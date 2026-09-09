"""Propose a course outline (units -> lessons with page ranges) from a PDF.

Used by the auto-structure upload flow: the teacher uploads a PDF, we ask Gemini
to detect its structure, the teacher confirms/edits it, then we ingest per the
outline. If the model output cannot be parsed, we fall back to one unit so this
never fails hard.
"""

import json
import re

from django.conf import settings
from openai import OpenAI

from courses.services.pdf_extractor import PageText


OUTLINE_MODEL = "gemini-3.1-flash-lite"
DEFAULT_UNIT_NAME = "Course Information"
DEFAULT_LESSON_NAME = "General"

SYSTEM_PROMPT = (
    "You organize a course document into a clean outline of units and lessons, "
    "using the document's own headings. Output STRICT JSON only, no prose."
)


class OutlineError(Exception):
    """Raised only when we cannot even attempt an outline (e.g. no key)."""
    pass


def _page_map(pages: list[PageText]) -> str:
    """One short line per page (its opening text), where headings usually live."""
    lines = []
    for p in pages:
        snippet = " ".join(p.text.split())[:300]
        lines.append(f"Page {p.page_number}: {snippet}")
    return "\n".join(lines)


def _parse_json(text: str) -> dict:
    """Parse the model's JSON, tolerating ```json fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def propose_outline(pages: list[PageText]) -> list[dict]:
    """Return a list of segments: {unit, lesson, page_start, page_end}.

    Always returns at least one segment (a single-unit fallback), so the caller
    can rely on getting something usable.
    """
    if not pages:
        return []

    max_page = max(p.page_number for p in pages)
    fallback = [{
        "unit": DEFAULT_UNIT_NAME, "lesson": DEFAULT_LESSON_NAME,
        "page_start": 1, "page_end": max_page,
    }]

    if not settings.GEMINI_API_KEY:
        raise OutlineError("GEMINI_API_KEY is not set")

    user_prompt = (
        "Group the pages below into units, and within each unit into lessons, "
        "based on the document's headings. Return JSON exactly like:\n"
        '{"units":[{"name":"...","lessons":[{"name":"...","page_start":1,"page_end":3}]}]}\n'
        f"Page numbers are 1-based and must cover 1..{max_page}. Keep names short.\n\n"
        f"Pages:\n{_page_map(pages)}"
    )

    client = OpenAI(api_key=settings.GEMINI_API_KEY, base_url=settings.GEMINI_BASE_URL)
    try:
        response = client.chat.completions.create(
            model=OUTLINE_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
        data = _parse_json(response.choices[0].message.content)
    except Exception:
        return fallback   # never fail hard: one unit covering the whole document

    segments = []
    for unit in data.get("units", []):
        unit_name = (unit.get("name") or DEFAULT_UNIT_NAME).strip()
        for lesson in unit.get("lessons", []):
            try:
                start = max(1, int(lesson.get("page_start", 1)))
                end = min(max_page, int(lesson.get("page_end", max_page)))
            except (TypeError, ValueError):
                start, end = 1, max_page
            if end < start:
                end = start
            segments.append({
                "unit": unit_name,
                "lesson": (lesson.get("name") or DEFAULT_LESSON_NAME).strip(),
                "page_start": start,
                "page_end": end,
            })

    return segments or fallback

"""Turn retrieved chunks into a grounded answer using Google Gemini.

We call Gemini through its OpenAI-compatible API, so the same `openai` client
works, just pointed at Gemini with a Gemini model name.
"""

from django.conf import settings
from openai import OpenAI

from courses.services.retriever import RetrievedChunk


ANSWER_MODEL = "gemini-3.1-flash-lite"

# The rulebook we give the model: answer ONLY from the excerpts, never invent.
SYSTEM_PROMPT = (
    "You are a helpful course assistant. Answer the student's question using ONLY "
    "the course excerpts provided. If the answer is not in them, say you cannot "
    "find it in the course materials. Be clear and concise. Never invent facts."
)


class GenerationError(Exception):
    """Raised when the answer cannot be generated."""
    pass


def _loc(c: RetrievedChunk) -> str:
    """Short location for an excerpt label: 'slide 15' / 'section X' / 'page 42'."""
    if c.location_kind == "slide" and c.location_value:
        return f"slide {c.location_value}"
    if c.location_kind == "section":
        return f"section {c.location_label}".strip()
    if c.location_value:
        return f"page {c.location_value}"
    if c.page_number:
        return f"page {c.page_number}"
    return ""


def _build_context(chunks: list[RetrievedChunk]) -> str:
    """Lay the chunks out as numbered, labelled excerpts for the model.

    Each excerpt is tagged with its file and location, so the model can pull
    from several files and the answer stays grounded across them.
    """
    parts = []
    for i, c in enumerate(chunks, start=1):
        label = f"[{i}] {c.file_name} ({_loc(c)})"
        parts.append(f"{label}\n{c.chunk_text}")
    return "\n\n".join(parts)


def generate_answer(question: str, chunks: list[RetrievedChunk], history=None) -> str:
    """Write an answer to the question, grounded in the given chunks.

    `history` is an optional list of prior turns [{"question", "answer"}, ...],
    so the model understands follow-ups like "explain that more simply".
    """
    if not settings.GEMINI_API_KEY:
        raise GenerationError("GEMINI_API_KEY is not set")

    user_prompt = f"Course excerpts:\n{_build_context(chunks)}\n\nQuestion: {question}"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in (history or []):
        messages.append({"role": "user", "content": turn["question"]})
        messages.append({"role": "assistant", "content": turn["answer"]})
    messages.append({"role": "user", "content": user_prompt})

    client = OpenAI(api_key=settings.GEMINI_API_KEY, base_url=settings.GEMINI_BASE_URL)
    try:
        response = client.chat.completions.create(
            model=ANSWER_MODEL,
            messages=messages,
            temperature=0.2,   # low = stay factual, less creative
        )
    except Exception as error:
        raise GenerationError(f"Gemini answer request failed: {error}")

    return response.choices[0].message.content.strip()

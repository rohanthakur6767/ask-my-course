"""Split a student's question into separate sub-questions.

This lets us handle MIXED questions like
  "What is photosynthesis, and who is the president of India?"
by answering each part on its own: the part that is in the course gets a grounded
answer with citations, and the part that is not gets a clear "outside the course
materials" - never answered from the model's general knowledge.

If splitting fails or the question is really single, we return it as one item,
so behaviour degrades safely to the normal single-question flow.
"""

from django.conf import settings
from openai import OpenAI


DECOMPOSE_MODEL = "gemini-3.1-flash-lite"
MAX_PARTS = 5   # safety cap, so one question cannot fan out into many LLM calls

_PROMPT = (
    "Split the student's question into separate, self-contained sub-questions - "
    "one per line, with NO numbering or bullets. Only split when the question truly "
    "asks about different things. If it is really a single question (including "
    "'difference between X and Y'), return it unchanged as one line.\n\n"
    "Question: {q}"
)


def decompose_question(question: str) -> list[str]:
    """Return the sub-questions (always at least one). Never raises."""
    question = (question or "").strip()
    if not question or not settings.GEMINI_API_KEY:
        return [question] if question else []

    try:
        client = OpenAI(api_key=settings.GEMINI_API_KEY, base_url=settings.GEMINI_BASE_URL)
        resp = client.chat.completions.create(
            model=DECOMPOSE_MODEL,
            messages=[{"role": "user", "content": _PROMPT.format(q=question)}],
            temperature=0,
        )
        parts = []
        for line in resp.choices[0].message.content.splitlines():
            cleaned = line.strip().lstrip("-*0123456789.) ").strip()
            if cleaned:
                parts.append(cleaned)
        return parts[:MAX_PARTS] if parts else [question]
    except Exception:
        # Any failure: fall back to treating it as one question.
        return [question]

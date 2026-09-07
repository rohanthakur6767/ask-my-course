"""Generation: turn retrieved chunks into a grounded answer."""

from django.conf import settings
from openai import OpenAI

from courses.services.retriever import RetrievedChunk


ANSWER_MODEL = "gpt-4o-mini"

# The rulebook we give the model: answer ONLY from the excerpts, never invent.
SYSTEM_PROMPT = (
    "You are a helpful course assistant. Answer the student's question using ONLY "
    "the course excerpts provided. If the answer is not in them, say you cannot "
    "find it in the course materials. Be clear and concise. Never invent facts."
)


class GenerationError(Exception):
    """Raised when the answer cannot be generated."""
    pass


def _build_context(chunks: list[RetrievedChunk]) -> str:
    """Lay the chunks out as numbered, labelled excerpts for the model."""
    parts = []
    for i, c in enumerate(chunks, start=1):
        label = f"[{i}] {c.unit_name} > {c.lesson_name} (page {c.page_number})"
        parts.append(f"{label}\n{c.chunk_text}")
    return "\n\n".join(parts)


def _fake_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """Offline stub: no LLM, just prove the context flows through."""
    if not chunks:
        return "I could not find this in the course materials."
    top = chunks[0]
    return (
        f"(offline draft) From {top.unit_name} > {top.lesson_name} "
        f"(page {top.page_number}): {top.chunk_text[:200]}"
    )


def generate_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """Write an answer to the question, grounded in the given chunks."""
    if getattr(settings, "USE_FAKE_LLM", True):
        return _fake_answer(question, chunks)

    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise GenerationError("OPENAI_API_KEY is not set")

    user_prompt = (
        f"Course excerpts:\n{_build_context(chunks)}\n\nQuestion: {question}"
    )

    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=ANSWER_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,   # low = stay factual, less creative
        )
    except Exception as error:
        raise GenerationError(f"OpenAI answer request failed: {error}")

    return response.choices[0].message.content.strip()
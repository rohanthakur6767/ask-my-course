"""The /ask flow: retrieve, guard, generate, log, and return."""

from courses.models import Course, ChatSession
from courses.services.retriever import retrieve
from courses.services.generator import generate_answer


GUARDRAIL_THRESHOLD = 0.5   # refuse if the best match is weaker than this
REFUSAL_MESSAGE = (
    "I can only answer from this course's materials, and I could not find the "
    "answer there. Please rephrase, or ask your teacher to add it."
)


class AskError(Exception):
    """Raised when the question cannot be answered (e.g. course missing)."""
    pass


def answer_question(course_id: str, question: str, user_id: str = "", top_k: int = 5) -> dict:
    """Answer a student's question, grounded only in the course materials."""
    if not Course.objects.filter(id=course_id).exists():
        raise AskError(f"Course not found: {course_id}")

    chunks = retrieve(course_id, question, top_k=top_k)

    # Guardrail: if there is nothing, or the best match is too weak, refuse.
    top_score = chunks[0].score if chunks else 0.0
    guardrail_triggered = top_score < GUARDRAIL_THRESHOLD

    if guardrail_triggered:
        answer = REFUSAL_MESSAGE
        sources = []
    else:
        answer = generate_answer(question, chunks)
        sources = [
            {
                "unit": c.unit_name,
                "lesson": c.lesson_name,
                "page": c.page_number,
                "relevance_score": round(c.score, 3),
            }
            for c in chunks
        ]

    confidence = round(top_score, 3)

    # Log every exchange (powers history and evaluation later).
    ChatSession.objects.create(
        course_id=course_id,
        user_id=user_id,
        question=question,
        answer=answer,
        sources=sources,
        confidence=confidence,
        guardrail_triggered=guardrail_triggered,
    )

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "guardrail_triggered": guardrail_triggered,
    }
"""The /ask flow: small talk, history, retrieve, guard, generate, log, and return."""

import re

from courses.models import Course, ChatSession
from courses.services.retriever import retrieve
from courses.services.generator import generate_answer


GUARDRAIL_THRESHOLD = 0.5   # refuse if the best match is weaker than this
HISTORY_TURNS = 3           # how many prior turns to feed the model for context
REFUSAL_MESSAGE = (
    "I can only answer from this course's materials, and I could not find the "
    "answer there. Please rephrase, or ask your teacher to add it."
)

# A warm reply for greetings / small talk, so we do not coldly refuse a hello.
SMALLTALK_MESSAGE = (
    "Hi! I'm the assistant for this course. Ask me anything about the course "
    "materials and I'll answer with sources. What would you like to know?"
)
_GREETING_RE = re.compile(
    r"^\s*("
    r"(hi+|hey+|hello+|yo|hiya|hola|namaste)([\s,!.]*(there|everyone|all))?"
    r"|(hi|hey|hello)?\s*how are you( doing)?"
    r"|good\s+(morning|afternoon|evening)"
    r"|thank\s*you|thanks|thankyou|thank\s*u|ty|thx|cheers|much appreciated|appreciate it"
    r"|bye|goodbye|see you"
    r"|who are you|what can you do|what do you do|what is this|help"
    # Optional polite trailing words, so "thank you so much" / "thanks a lot" /
    # "good morning sir" still count. Fully anchored, so a real question (which
    # carries content beyond these fillers) can never match.
    r")(\s+(so much|very much|a lot|again|please|buddy|mate|sir|ma'?am|guys|team|everyone|all|there|friend))*"
    r"[\s,!.?]*$"
)

# Phrases the model uses when it declines because the answer is not in the
# excerpts. Kept tight (meta-refusal wording, not ordinary content) so a normal
# grounded answer is never mistaken for a refusal.
_REFUSAL_HINTS = (
    "i cannot find", "i could not find", "cannot find the answer",
    "could not find the answer", "i can only answer", "the excerpts do not",
    "the materials do not", "no information about", "i cannot answer",
    "cannot answer this",
)


class AskError(Exception):
    """Raised when the question cannot be answered (e.g. course missing)."""
    pass


def _is_smalltalk(question: str) -> bool:
    """True for greetings / small talk (hi, hello, how are you, thanks...)."""
    return bool(_GREETING_RE.match(question.lower()))


def _looks_like_refusal(answer: str) -> bool:
    """True when the model's answer is itself a 'not in the materials' refusal."""
    low = answer.lower()
    return any(hint in low for hint in _REFUSAL_HINTS)


def answer_question(course_id: str, question: str, user_id: str = "", top_k: int = 5,
                    conversation_id=None) -> dict:
    """Answer a student's question, grounded only in the course materials.

    If conversation_id is given, the last few turns of that conversation are fed
    to the model so follow-up questions keep context.
    """
    if not Course.objects.filter(id=course_id).exists():
        raise AskError(f"Course not found: {course_id}")

    conv = str(conversation_id) if conversation_id else None

    # Prior turns of this conversation (the most recent few, real answers only).
    history = []
    if conversation_id:
        prior = list(
            ChatSession.objects
            .filter(course_id=course_id, conversation_id=conversation_id, guardrail_triggered=False)
            .order_by("created_at")
        )
        history = [{"question": t.question, "answer": t.answer} for t in prior[-HISTORY_TURNS:]]

    # Greetings / small talk get a friendly reply, not a cold guardrail refusal.
    if _is_smalltalk(question):
        ChatSession.objects.create(
            course_id=course_id, user_id=user_id, conversation_id=conversation_id,
            question=question, answer=SMALLTALK_MESSAGE, sources=[], confidence=0.0,
            guardrail_triggered=False,
        )
        return {"answer": SMALLTALK_MESSAGE, "sources": [], "confidence": 0.0,
                "guardrail_triggered": False, "conversation_id": conv}

    # For a follow-up, anchor the search with the previous question so a vague
    # question ("explain that") still retrieves the right chunks.
    retrieval_query = question
    if history:
        retrieval_query = f"{history[-1]['question']} {question}"

    chunks = retrieve(course_id, retrieval_query, top_k=top_k)

    # Guardrail: if there is nothing, or the best match is too weak, refuse.
    top_score = chunks[0].score if chunks else 0.0
    guardrail_triggered = top_score < GUARDRAIL_THRESHOLD

    if guardrail_triggered:
        answer = REFUSAL_MESSAGE
        sources = []
    else:
        answer = generate_answer(question, chunks, history=history)
        # Second guardrail layer: the model may (correctly) decline when the
        # retrieved chunks do not actually contain the answer, even though the top
        # score cleared the threshold. Treat that as a refusal so the UI shows the
        # refusal card instead of a weak "answer" with misleading sources.
        if _looks_like_refusal(answer):
            guardrail_triggered = True
            answer = REFUSAL_MESSAGE
            sources = []
        else:
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

    ChatSession.objects.create(
        course_id=course_id, user_id=user_id, conversation_id=conversation_id,
        question=question, answer=answer, sources=sources, confidence=confidence,
        guardrail_triggered=guardrail_triggered,
    )

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "guardrail_triggered": guardrail_triggered,
        "conversation_id": conv,
    }

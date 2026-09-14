"""The /ask flow: small talk, history, retrieve, guard, generate, log, and return."""

import re

from courses.models import Course, ChatSession
from courses.services.retriever import retrieve
from courses.services.generator import generate_answer, generate_combined
from courses.services.decomposer import decompose_question


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


def _looks_multipart(question: str) -> bool:
    """Cheap check for whether a question might contain several parts. We only pay
    for the decomposition LLM call when this is true, so simple questions stay fast."""
    low = question.lower()
    return (" and " in low) or (";" in question) or (" also " in low) or (question.count("?") > 1)


def _location_label(c) -> str:
    """A human-readable location for a citation: 'Page 42' / 'Slide 15' / 'Section: X'."""
    if c.location_kind == "page" and c.location_value:
        return f"Page {c.location_value}"
    if c.location_kind == "slide" and c.location_value:
        return f"Slide {c.location_value}"
    if c.location_kind == "section":
        return f"Section: {c.location_label}" if c.location_label else "Section"
    if c.page_number:
        return f"Page {c.page_number}"
    return ""


def _citation_link(c) -> str:
    """A link that opens the viewable PDF at the right page/slide.

    Every type now has a viewable PDF (native for PDFs, a converted copy for
    DOCX/PPTX), so Open works uniformly. Blank if no PDF was produced.
    """
    if not c.pdf_url:
        return ""
    if c.location_value:
        return f"{c.pdf_url}#page={c.location_value}"
    return c.pdf_url


def _build_sources(chunks) -> list[dict]:
    """Turn retrieved chunks into clean, file-centric citations for the UI."""
    sources = []
    for c in chunks:
        sources.append({
            "file_name": c.file_name,
            "file_type": c.file_type,
            "location_kind": c.location_kind,
            "location_value": c.location_value,
            "location_label": _location_label(c),
            "link": _citation_link(c),
            "source_url": c.source_url,
            # kept for backward compatibility with the older citation shape
            "unit": c.unit_name,
            "lesson": c.lesson_name,
            "page": c.page_number,
            "relevance_score": round(c.score, 3),
        })
    return sources


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

    # Split a MIXED question into parts - but only when it looks multi-part and is
    # a fresh question (not a follow-up). Each part is judged on its own, so we can
    # answer the covered parts and refuse the rest, never using outside knowledge.
    parts = [question]
    if not history and _looks_multipart(question):
        parts = decompose_question(question)

    if len(parts) <= 1:
        # --- Single-question flow ---
        # For a follow-up, anchor the search with the previous question so a vague
        # question ("explain that") still retrieves the right chunks.
        retrieval_query = question
        if history:
            retrieval_query = f"{history[-1]['question']} {question}"

        chunks = retrieve(course_id, retrieval_query, top_k=top_k)
        top_score = chunks[0].score if chunks else 0.0
        guardrail_triggered = top_score < GUARDRAIL_THRESHOLD

        if guardrail_triggered:
            answer = REFUSAL_MESSAGE
            sources = []
        else:
            answer = generate_answer(question, chunks, history=history)
            # Second guardrail layer: the model may (correctly) decline when the
            # retrieved chunks do not actually contain the answer, even though the
            # top score cleared the threshold. Treat that as a refusal.
            if _looks_like_refusal(answer):
                guardrail_triggered = True
                answer = REFUSAL_MESSAGE
                sources = []
            else:
                sources = _build_sources(chunks)
        confidence = round(top_score, 3)
    else:
        # --- Mixed-question flow: judge each part on its own ---
        covered, uncovered, best_scores = [], [], []
        for part in parts:
            pchunks = retrieve(course_id, part, top_k=top_k)
            ptop = pchunks[0].score if pchunks else 0.0
            if ptop >= GUARDRAIL_THRESHOLD:
                covered.append({"question": part, "chunks": pchunks})
                best_scores.append(ptop)
            else:
                uncovered.append(part)

        if not covered:
            # No part of the question is in the course -> refuse the whole thing.
            answer = REFUSAL_MESSAGE
            sources = []
            guardrail_triggered = True
            confidence = 0.0
        else:
            answer = generate_combined(question, covered, uncovered, history=history)
            # Merge + de-duplicate the covered chunks into one clean source list.
            merged, seen = [], set()
            for part in covered:
                for ch in part["chunks"]:
                    key = (ch.file_name, ch.location_kind, ch.location_value, ch.chunk_text[:80])
                    if key not in seen:
                        seen.add(key)
                        merged.append(ch)
            merged.sort(key=lambda c: c.score, reverse=True)
            sources = _build_sources(merged[:top_k])
            guardrail_triggered = False
            confidence = round(max(best_scores), 3)

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

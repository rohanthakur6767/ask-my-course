"""Retrieval: find the chunks most similar to a question, within one course."""

from dataclasses import dataclass

from pgvector.django import CosineDistance

from courses.models import Embedding
from courses.services.embedder import embed_text


DEFAULT_TOP_K = 5


@dataclass
class RetrievedChunk:
    """One search hit, with everything needed to cite it."""
    chunk_text: str
    unit_name: str
    lesson_name: str
    page_number: int | None
    # File-centric citation info (works across PDF / DOCX / PPTX):
    file_name: str
    file_type: str
    source_url: str
    location_kind: str            # "page" | "slide" | "section"
    location_value: int | None
    location_label: str
    score: float   # cosine similarity, higher = closer (1.0 = identical)


def retrieve(course_id: str, question: str, top_k: int = DEFAULT_TOP_K) -> list[RetrievedChunk]:
    """Embed the question and return the top_k nearest chunks in this course.

    The search runs over ALL chunks in the course, so the results naturally span
    every file type - one question, one search across the whole course.
    """
    if not question.strip():
        raise ValueError("question must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")

    # Same model as the chunks, so question and chunks live in the same space.
    query_vector = embed_text(question)

    # CosineDistance = 1 - similarity, so smaller distance = more similar.
    # The database does the search using the HNSW index.
    rows = (
        Embedding.objects
        .filter(course_id=course_id)              # only this course (multi-tenant safe)
        .select_related("material")               # so we can read file_type / source_url
        .annotate(distance=CosineDistance("embedding", query_vector))
        .order_by("distance")[:top_k]             # nearest first, take top_k
    )

    return [
        RetrievedChunk(
            chunk_text=row.chunk_text,
            unit_name=row.unit_name,
            lesson_name=row.lesson_name,
            page_number=row.page_number,
            file_name=row.file_name or row.material.file_name,
            file_type=row.material.file_type,
            source_url=row.material.source_url,
            location_kind=row.location_kind or ("page" if row.page_number else ""),
            location_value=row.location_value if row.location_value is not None else row.page_number,
            location_label=row.location_label,
            score=1 - row.distance,               # back to similarity (higher = closer)
        )
        for row in rows
    ]
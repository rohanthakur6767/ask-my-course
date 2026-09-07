"""Step 4 of ingestion: run the whole pipeline and save the results.

It ties the pieces together:
  extract (PDF -> pages) -> chunk (pages -> chunks) -> embed (chunks -> vectors)
  -> store (Material + Embedding rows in the database).

It also fills the course hierarchy (Unit, Lesson) as needed, following the rule
we agreed on: never guess a value, use the given names or a clear default, and
create parent rows only when they are missing.
"""

import time
from pathlib import Path

from django.db import transaction

from courses.models import Course, Unit, Lesson, Material, Embedding
from courses.services.pdf_extractor import extract_pages
from courses.services.chunker import chunk_pages
from courses.services.embedder import embed_texts


# Course-wide materials (like a syllabus) may not belong to a real lesson, so
# they land under these clearly named defaults. Kept as constants here, not as
# magic strings scattered through the code.
DEFAULT_UNIT_NAME = "Course Information"
DEFAULT_LESSON_NAME = "General"


class IngestError(Exception):
    """Raised when ingestion cannot complete (course missing, no chunks, etc.)."""
    pass


def ingest_material(
    course_id: str,
    file_path: str,
    unit_name: str = "",
    lesson_name: str = "",
    file_name: str = "",
    file_type: str = "pdf",
    material_type: str = Material.MaterialType.PDF,
) -> dict:
    """Ingest one file into a course: extract, chunk, embed, and store.

    Args:
        course_id: the course this material belongs to (must already exist).
        file_path: path to the PDF on disk.
        unit_name: unit to file it under; defaults to "Course Information".
        lesson_name: lesson to file it under; defaults to "General".
        file_name: display name; defaults to the file's own name.
        file_type: e.g. "pdf".
        material_type: one of Material.MaterialType (pdf / syllabus / note).

    Returns:
        A summary dict: status, material_id, chunks_created, pages_processed,
        processing_time_ms.

    Raises:
        IngestError: if the course is missing or the file has no usable text.
        PdfExtractionError / EmbeddingError: bubble up from the steps.
    """
    started = time.monotonic()

    # The course must already exist (its id came from the URL). We never create
    # a course here, we only attach to one.
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        raise IngestError(f"Course not found: {course_id}")

    # Clean the inputs and apply clear defaults. We never invent a name from the
    # file's content; a missing name becomes a documented default, not a guess.
    unit_name = (unit_name or DEFAULT_UNIT_NAME).strip()
    lesson_name = (lesson_name or DEFAULT_LESSON_NAME).strip()
    file_name = (file_name or Path(file_path).name).strip()

    # --- Heavy work FIRST, outside the database transaction ---
    # Extracting and embedding can be slow (embedding hits the network in real
    # mode), and we do not want to hold a database transaction open while we wait.
    pages = extract_pages(file_path)                          # may raise PdfExtractionError
    chunks = chunk_pages(pages)

    if not chunks:
        raise IngestError(f"No chunks produced from file: {file_path}")

    vectors = embed_texts([chunk.text for chunk in chunks])   # may raise EmbeddingError

    # --- Fast database writes, inside ONE transaction (all or nothing) ---
    with transaction.atomic():
        # Fill the hierarchy: reuse the unit/lesson if they exist, else create.
        unit, _ = Unit.objects.get_or_create(course=course, name=unit_name)
        lesson, _ = Lesson.objects.get_or_create(unit=unit, name=lesson_name)

        # Reuse the material if this exact file was ingested before (same lesson
        # + same file name), so a re-upload updates it instead of duplicating.
        material, created = Material.objects.get_or_create(
            lesson=lesson,
            file_name=file_name,
            defaults={
                "file_path": file_path,
                "file_type": file_type,
                "material_type": material_type,
            },
        )
        if not created:
            # Re-ingest: refresh the fields and drop the old chunks, so we never
            # pile up duplicate embeddings. This is the "idempotent" behaviour.
            material.file_path = file_path
            material.file_type = file_type
            material.material_type = material_type
            material.save()
            material.embeddings.all().delete()

        # Build all Embedding rows in memory, then insert them in ONE query.
        rows = [
            Embedding(
                material=material,
                course=course,
                chunk_text=chunk.text,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                unit_name=unit.name,       # denormalized, for fast citations
                lesson_name=lesson.name,   # denormalized, for fast citations
                embedding=vector,
            )
            for chunk, vector in zip(chunks, vectors)
        ]
        Embedding.objects.bulk_create(rows)

    elapsed_ms = int((time.monotonic() - started) * 1000)

    return {
        "status": "success",
        "material_id": str(material.id),
        "chunks_created": len(rows),
        "pages_processed": len(pages),
        "processing_time_ms": elapsed_ms,
    }
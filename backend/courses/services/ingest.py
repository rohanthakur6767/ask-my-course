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

from django.conf import settings
from django.db import transaction

from courses.models import Course, Unit, Lesson, Material, Embedding
from courses.services.pdf_extractor import extract_pages
from courses.services.chunker import chunk_pages, chunk_segments
from courses.services.extractors import extract_segments, file_type_of
from courses.services.converter import convert_to_pdf, ConversionError
from courses.services.embedder import embed_texts
from courses.services.storage import storage_enabled, upload_file, safe_key


# Course-wide materials (like a syllabus) may not belong to a real lesson, so
# they land under these clearly named defaults. Kept as constants here, not as
DEFAULT_UNIT_NAME = "Course Information"
DEFAULT_LESSON_NAME = "General"


def _media_url(file_path: str) -> str:
    """Turn a saved file path into a link the browser can open, served by Django
    from MEDIA_ROOT. Works locally; on an ephemeral cloud host use cloud storage
    (see _file_url). This stays the safe fallback when storage is off."""
    try:
        rel = Path(file_path).resolve().relative_to(Path(settings.MEDIA_ROOT).resolve())
        return settings.MEDIA_URL + str(rel).replace("\\", "/")
    except Exception:
        return ""


def _file_url(file_path: str, course_id: str, file_type: str = "", *, as_pdf: bool = False) -> str:
    """Public URL for a saved file: Supabase Storage when configured (so links
    work on the deployed site), otherwise the local /media/ URL.

    `as_pdf` marks the viewable-PDF copy (native for PDFs, converted for
    DOCX/PPTX) so it lands under a separate bucket prefix and is served as a PDF.
    """
    if not file_path:
        return ""
    if storage_enabled():
        prefix = "pdf" if as_pdf else "sources"
        key = safe_key(prefix, course_id, Path(file_path).name)
        url = upload_file(file_path, key, file_type="pdf" if as_pdf else file_type)
        if url:
            return url
    # Storage off or upload failed: fall back to the local media URL.
    return _media_url(file_path)


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
    file_type = (file_type or file_type_of(file_path) or "pdf").lower()

    # --- Heavy work FIRST, outside the database transaction ---
    # Also build a viewable PDF so citations can open at the exact page/slide:
    #  - PDF  : the file itself (extract by page)
    #  - PPTX : keep slide text incl. notes; slide N == PDF page N in the copy
    #  - DOCX : convert to PDF, then extract THAT by page (real, deep-linkable pages)
    pdf_path = None
    if file_type == "pdf":
        segments = extract_segments(file_path, "pdf")
        pdf_path = file_path
    elif file_type == "pptx":
        segments = extract_segments(file_path, "pptx")
        try:
            pdf_path = convert_to_pdf(file_path)
        except ConversionError:
            pdf_path = None            # still ingest; just no inline "Open"
    elif file_type == "docx":
        try:
            pdf_path = convert_to_pdf(file_path)
            segments = extract_segments(pdf_path, "pdf")       # page-based, deep-linkable
        except ConversionError:
            segments = extract_segments(file_path, "docx")     # fallback: sections, no deep-link
            pdf_path = None
    else:
        segments = extract_segments(file_path, file_type)      # may raise ExtractionError

    chunks = chunk_segments(segments)

    if not chunks:
        raise IngestError(f"No chunks produced from file: {file_path}")

    vectors = embed_texts([chunk.text for chunk in chunks])   # may raise EmbeddingError

    # Publish the files (upload to cloud storage if configured, else a media URL).
    # Done here, outside the transaction, since an upload is network I/O. For a
    # native PDF the download and the viewable copy are the same file, so upload
    # it once and reuse the URL.
    source_url = _file_url(file_path, str(course.id), file_type=file_type)
    if pdf_path and Path(pdf_path).resolve() == Path(file_path).resolve():
        pdf_url = source_url
    elif pdf_path:
        pdf_url = _file_url(pdf_path, str(course.id), as_pdf=True)
    else:
        pdf_url = ""

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
                "source_url": source_url,
                "pdf_url": pdf_url,
                "material_type": material_type,
            },
        )
        if not created:
            # Re-ingest: refresh the fields and drop the old chunks, so we never
            # pile up duplicate embeddings. This is the "idempotent" behaviour.
            material.file_path = file_path
            material.file_type = file_type
            material.source_url = source_url
            material.pdf_url = pdf_url
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
                location_kind=chunk.location_kind,     # page / slide / section
                location_value=chunk.location_value,
                location_label=chunk.location_label,
                file_name=material.file_name,           # denormalized, file-centric citations
                unit_name=unit.name,       # denormalized, for fast citations
                lesson_name=lesson.name,   # denormalized, for fast citations
                embedding=vector,
            )
            for chunk, vector in zip(chunks, vectors)
        ]
        Embedding.objects.bulk_create(rows) # Insert all embedding rows into the database in one bulk operation.

    elapsed_ms = int((time.monotonic() - started) * 1000)

    return {
        "status": "success",
        "material_id": str(material.id),
        "chunks_created": len(rows),
        "pages_processed": len(segments),
        "processing_time_ms": elapsed_ms,
    }


def ingest_structured(
    course_id: str,
    file_path: str,
    outline: list[dict],
    file_name: str = "",
    file_type: str = "pdf",
    material_type: str = Material.MaterialType.PDF,
) -> dict:
    """Ingest one PDF split across many units/lessons, per a confirmed outline.

    `outline` is a list of {unit, lesson, page_start, page_end}. Each segment
    becomes its own Material (under its unit + lesson) holding that page range's
    chunks, so a single PDF builds a full Course -> Unit -> Lesson tree.
    """
    started = time.monotonic()

    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        raise IngestError(f"Course not found: {course_id}")
    if not outline:
        raise IngestError("Outline is empty")

    file_name = (file_name or Path(file_path).name).strip()

    # --- Heavy work first (extract, chunk, embed), outside the transaction ---
    pages = extract_pages(file_path)
    page_by_num = {p.page_number: p for p in pages}

    prepared = []       # (unit_name, lesson_name, [chunks]) for each non-empty segment
    all_texts = []
    for seg in outline:
        unit_name = (str(seg.get("unit", "")) or DEFAULT_UNIT_NAME).strip()
        lesson_name = (str(seg.get("lesson", "")) or DEFAULT_LESSON_NAME).strip()
        start = int(seg.get("page_start", 1))
        end = int(seg.get("page_end", start))
        seg_pages = [page_by_num[n] for n in range(start, end + 1) if n in page_by_num]
        chunks = chunk_pages(seg_pages)
        if not chunks:
            continue
        prepared.append((unit_name, lesson_name, chunks))
        all_texts.extend(c.text for c in chunks)

    if not all_texts:
        raise IngestError("No text found for the given outline")

    all_vectors = embed_texts(all_texts)   # one batched embedding call for the whole file

    # Publish once (cloud storage or media URL). It is a PDF, so the same file is
    # both the download and the viewable copy, and every segment shares this URL.
    url = _file_url(file_path, str(course.id), file_type=file_type)

    # --- Fast DB writes inside one transaction ---
    total_chunks = 0
    material_ids = []
    v = 0
    with transaction.atomic():
        for unit_name, lesson_name, chunks in prepared:
            unit, _ = Unit.objects.get_or_create(course=course, name=unit_name)
            lesson, _ = Lesson.objects.get_or_create(unit=unit, name=lesson_name)

            material, created = Material.objects.get_or_create(
                lesson=lesson, file_name=file_name,
                defaults={"file_path": file_path, "file_type": file_type,
                          "source_url": url, "pdf_url": url, "material_type": material_type},
            )
            if not created:
                material.file_path = file_path
                material.file_type = file_type
                material.source_url = url
                material.pdf_url = url
                material.material_type = material_type
                material.save()
                material.embeddings.all().delete()

            rows = []
            for chunk in chunks:
                rows.append(Embedding(
                    material=material, course=course,
                    chunk_text=chunk.text, chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    location_kind=chunk.location_kind,
                    location_value=chunk.location_value,
                    location_label=chunk.location_label,
                    file_name=material.file_name,
                    unit_name=unit.name, lesson_name=lesson.name,
                    embedding=all_vectors[v],
                ))
                v += 1
            Embedding.objects.bulk_create(rows)
            total_chunks += len(rows)
            material_ids.append(str(material.id))

    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {
        "status": "success",
        "materials_created": len(material_ids),
        "material_ids": material_ids,
        "chunks_created": total_chunks,
        "pages_processed": len(pages),
        "processing_time_ms": elapsed_ms,
    }
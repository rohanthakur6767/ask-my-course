"""Pull text out of a course file, whatever its type (PDF, DOCX, PPTX).

Every file type is different, but we return ONE common shape - a list of
`Segment`s - so the rest of the pipeline (chunk -> embed -> store) does not care
which file type it came from. Each segment also remembers WHERE it came from
(page / slide / section), so we can build an exact citation later.
"""

from dataclasses import dataclass
from pathlib import Path

import docx          # python-docx, reads Word .docx
import pptx          # python-pptx, reads PowerPoint .pptx

from courses.services.pdf_extractor import extract_pages, PdfExtractionError


@dataclass
class Segment:
    """A piece of a document with its location. The common unit every file
    type is turned into before chunking."""
    text: str
    location_kind: str          # "page" | "slide" | "section"
    location_value: int | None  # page/slide number; None for a DOCX section
    location_label: str         # e.g. a DOCX heading; "" if none


class ExtractionError(Exception):
    """Raised when a file cannot be read (missing, corrupt, unsupported)."""
    pass


# The file types we can read today. Old formats (.doc/.ppt) are not supported.
SUPPORTED_TYPES = ("pdf", "docx", "pptx")


def _extract_pdf(file_path: str) -> list[Segment]:
    """PDF -> one segment per page (page numbers are reliable in PDFs)."""
    try:
        pages = extract_pages(file_path)   # reuse the existing, tested PDF reader
    except PdfExtractionError as error:
        raise ExtractionError(str(error))
    return [Segment(p.text, "page", p.page_number, "") for p in pages]


def _extract_docx(file_path: str) -> list[Segment]:
    """DOCX -> one segment per section (grouped under each heading).

    Word files have no real page numbers (pages only exist when Word renders
    the file), so we use headings as the location instead.
    """
    try:
        document = docx.Document(file_path)
    except Exception as error:
        raise ExtractionError(f"Could not open DOCX: {file_path} ({error})")

    segments: list[Segment] = []
    current_label = "Document"     # default section name until we meet a heading
    current_text: list[str] = []
    index = 0

    def flush():
        nonlocal index, current_text
        body = " ".join(current_text).strip()
        if body:
            index += 1
            segments.append(Segment(body, "section", index, current_label))
        current_text = []

    for para in document.paragraphs:
        text = para.text.strip()
        style = (para.style.name or "") if para.style else ""
        if style.startswith("Heading") and text:
            flush()                # close the previous section
            current_label = text   # start a new one under this heading
        elif text:
            current_text.append(text)
    flush()                        # don't forget the last section

    if not segments:
        raise ExtractionError(f"No readable text found in DOCX: {file_path}")
    return segments


def _extract_pptx(file_path: str) -> list[Segment]:
    """PPTX -> one segment per slide (slide numbers are reliable)."""
    try:
        presentation = pptx.Presentation(file_path)
    except Exception as error:
        raise ExtractionError(f"Could not open PPTX: {file_path} ({error})")

    segments: list[Segment] = []
    for number, slide in enumerate(presentation.slides, start=1):
        parts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                text = shape.text_frame.text.strip()
                if text:
                    parts.append(text)
        # Speaker notes often hold the real explanation, so include them.
        if slide.has_notes_slide:
            note = slide.notes_slide.notes_text_frame.text.strip()
            if note:
                parts.append(f"Notes: {note}")

        title = ""
        if slide.shapes.title and slide.shapes.title.text.strip():
            title = slide.shapes.title.text.strip()

        body = "\n".join(parts).strip()
        if body:
            segments.append(Segment(body, "slide", number, title))

    if not segments:
        raise ExtractionError(f"No readable text found in PPTX: {file_path}")
    return segments


def file_type_of(file_path: str) -> str:
    """The lowercase extension without the dot, e.g. 'pdf'."""
    return Path(file_path).suffix.lstrip(".").lower()


def extract_segments(file_path: str, file_type: str = "") -> list[Segment]:
    """Read any supported file and return its segments. Dispatches by type."""
    if not Path(file_path).exists():
        raise ExtractionError(f"File not found: {file_path}")

    ftype = (file_type or file_type_of(file_path)).lower()
    if ftype == "pdf":
        return _extract_pdf(file_path)
    if ftype == "docx":
        return _extract_docx(file_path)
    if ftype == "pptx":
        return _extract_pptx(file_path)
    raise ExtractionError(
        f"Unsupported file type '{ftype}'. Supported: {', '.join(SUPPORTED_TYPES)}."
    )

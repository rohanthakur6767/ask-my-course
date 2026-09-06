"""ingestion: pull raw text out of a PDF, one page at a time.
We keep the page number with each page's text, because when we build a
citation, we can tell the student exactly which page an answer came from.
"""
from dataclasses import dataclass
from pathlib import Path

import pymupdf 

@dataclass
class PageText: #used to create small object that holds related data
    """The text we pulled from a single PDF page."""
    page_number: int   # 1-based, so it matches the page number a human sees
    text: str          # the plain text of that page

class PdfExtractionError(Exception):
    """Used when there is a problem reading the PDF(custom)."""
    pass

def extract_pages(file_path: str) -> list[PageText]: # it takes a PDF file path and returns a list of PageText objects.

    path = Path(file_path)

    # Edge case 1: the file is simply not there.
    if not path.exists():
        raise PdfExtractionError(f"File not found: {file_path}") # if the pdf doesn't exist, stop and show our custom error

    # Edge case 2: opening can fail if the file is corrupt or not a PDF at all.
    try:
        doc = pymupdf.open(str(path))
    except Exception as error:
        raise PdfExtractionError(f"Could not open PDF: {file_path} ({error})")

    # try/finally makes sure we always close the file, even if we raise below.
    try:
        # Edge case 3: a locked / password protected PDF cannot be read.
        if doc.needs_pass: # Check if the PDF needs a password.
            raise PdfExtractionError(f"PDF is password protected: {file_path}") # If yes, stop the extraction.

        pages: list[PageText] = [] # Empty list to store the text and page number of each page

        # enumerate gives us the page and its position (0, 1, 2...) at once.
        for index, page in enumerate(doc):
            raw_text = page.get_text("text")   # "text" = plain reading-order text
            cleaned = raw_text.strip()

            # Edge case 4: skip blank pages (a cover image, or a scanned page
            # with no selectable text). No point storing empty content.
            if not cleaned:
                continue

            pages.append(PageText(page_number=index + 1, text=cleaned))

        # Edge case 5: zero readable text usually means a scanned (image-only)
        # PDF that would need OCR.
        if not pages:
            raise PdfExtractionError(
                f"No readable text found (is it a scanned image?): {file_path}"
            )

        return pages

    finally:
        doc.close()
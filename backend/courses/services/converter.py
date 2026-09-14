"""Convert a DOCX/PPTX into a PDF copy using LibreOffice (headless).

Why: browsers can open a PDF at an exact page (file.pdf#page=15) but cannot show
Word/PowerPoint at a spot. So we render a PDF copy at ingest and deep-link into
it. The original file is kept for download; the PDF copy is for viewing.

LibreOffice is a normal program (not a pip package). We find `soffice` on PATH,
via the SOFFICE_PATH env var, or in the usual install locations.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class ConversionError(Exception):
    """Raised when a file cannot be converted to PDF."""
    pass


def _find_soffice() -> str | None:
    """Locate the LibreOffice executable."""
    override = os.getenv("SOFFICE_PATH")
    if override and Path(override).exists():
        return override
    candidates = [
        shutil.which("soffice"),
        shutil.which("libreoffice"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/usr/bin/soffice",
        "/usr/bin/libreoffice",
        "/opt/libreoffice/program/soffice",
    ]
    for path in candidates:
        if path and Path(path).exists():
            return path
    return None


def soffice_available() -> bool:
    return _find_soffice() is not None


def convert_to_pdf(file_path: str) -> str:
    """Render `file_path` (docx/pptx) to a PDF next to it, and return the PDF path."""
    soffice = _find_soffice()
    if not soffice:
        raise ConversionError(
            "LibreOffice not found. Install it, or set SOFFICE_PATH to soffice(.exe)."
        )

    src = Path(file_path)
    out_dir = src.parent
    # A private profile dir avoids the 'LibreOffice is already running' clash when
    # the user (or another convert) has an instance open.
    profile = Path(tempfile.mkdtemp(prefix="lo_profile_")).as_uri()

    try:
        subprocess.run(
            [soffice, f"-env:UserInstallation={profile}", "--headless",
             "--convert-to", "pdf", "--outdir", str(out_dir), str(src)],
            check=True, capture_output=True, timeout=180,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or b"").decode(errors="ignore")[:200]
        raise ConversionError(f"LibreOffice conversion failed: {detail}")
    except subprocess.TimeoutExpired:
        raise ConversionError("LibreOffice conversion timed out.")

    pdf_path = src.with_suffix(".pdf")
    if not pdf_path.exists():
        raise ConversionError("Conversion ran but the PDF was not produced.")
    return str(pdf_path)

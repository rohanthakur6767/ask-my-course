"""Optional cloud file storage (Supabase Storage).

Local dev serves uploaded files from MEDIA_ROOT, which works on one machine but
not on an ephemeral cloud host: Render wipes its disk on every redeploy, and
Django does not serve media in production. When Supabase Storage is configured,
we upload each file to a public bucket and use the returned public URL for the
"Open" and "Download" citation links, so they work on the deployed site too.

Everything here is best-effort. If Supabase is not configured, or an upload
fails, callers fall back to the local /media/ URL. The app never breaks because
storage is off. We use the standard library (urllib) on purpose, so there is no
extra dependency to install on the server.
"""

import logging
import re
import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

# Content types we set explicitly; anything else uploads as a generic binary.
_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def storage_enabled() -> bool:
    """True only when all of the Supabase Storage settings are present."""
    return bool(
        getattr(settings, "SUPABASE_URL", "")
        and getattr(settings, "SUPABASE_SERVICE_KEY", "")
        and getattr(settings, "SUPABASE_BUCKET", "")
    )


def safe_key(*parts: str) -> str:
    """Build a clean bucket key from path parts (no spaces or odd characters)."""
    cleaned = []
    for part in parts:
        piece = str(part).strip().replace("\\", "/")
        # Keep letters, numbers, dot, dash, underscore, slash; replace the rest.
        piece = re.sub(r"[^A-Za-z0-9._/-]+", "_", piece).strip("/")
        if piece:
            cleaned.append(piece)
    return "/".join(cleaned)


def public_url_for_key(key: str) -> str:
    """The public download URL for an object already in the bucket."""
    base = settings.SUPABASE_URL.rstrip("/")
    return f"{base}/storage/v1/object/public/{settings.SUPABASE_BUCKET}/{key}"


def upload_file(local_path: str, key: str, file_type: str = "") -> str:
    """Upload a local file to the Supabase bucket and return its public URL.

    Overwrites any object already at the same key (so re-ingesting a file just
    refreshes it). Returns "" when storage is off or the upload fails, so the
    caller can fall back to the local media URL.
    """
    if not storage_enabled():
        return ""

    try:
        data = Path(local_path).read_bytes()
    except OSError as error:
        logger.warning("storage: cannot read %s: %s", local_path, error)
        return ""

    base = settings.SUPABASE_URL.rstrip("/")
    endpoint = f"{base}/storage/v1/object/{settings.SUPABASE_BUCKET}/{key}"
    headers = {
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "apikey": settings.SUPABASE_SERVICE_KEY,
        "x-upsert": "true",   # overwrite instead of failing if the key exists
        "Content-Type": _CONTENT_TYPES.get(file_type.lower(), "application/octet-stream"),
    }

    request = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            if resp.status not in (200, 201):
                logger.warning("storage: upload got status %s for %s", resp.status, key)
                return ""
    except urllib.error.HTTPError as error:
        body = ""
        try:
            body = error.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        logger.warning("storage: upload failed for %s: %s %s", key, error.code, body)
        return ""
    except urllib.error.URLError as error:
        logger.warning("storage: upload failed for %s: %s", key, error)
        return ""

    return public_url_for_key(key)

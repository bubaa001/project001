"""
Upload local files (FileField / ImageField content) to Supabase Storage
so the remote can reference them via public URLs.
"""
import os
import logging
from pathlib import Path
from typing import Optional
from django.conf import settings
from ONLportal.supabase_client import supabase

logger = logging.getLogger('sync_manager.file_uploader')

BUCKET_NAME = 'sync-uploads'


def ensure_bucket_exists() -> None:
    """Idempotent: create the sync-uploads bucket if it does not exist."""
    try:
        supabase.storage.get_bucket(BUCKET_NAME)
        logger.debug("Storage bucket '%s' already exists.", BUCKET_NAME)
    except Exception:
        logger.info("Creating storage bucket '%s'...", BUCKET_NAME)
        supabase.storage.create_bucket(
            BUCKET_NAME,
            options={'public': True},
        )


def upload_file(local_path: str) -> Optional[str]:
    """
    Upload a single file to Supabase Storage.

    Returns the public URL of the uploaded file, or None on failure.
    The remote path mirrors the MEDIA_ROOT-relative local path.
    """
    full_path = Path(local_path)
    if not full_path.exists():
        logger.warning("File not found, skipping: %s", local_path)
        return None

    media_root = Path(settings.MEDIA_ROOT)
    try:
        remote_name = str(full_path.relative_to(media_root)).replace('\\', '/')
    except ValueError:
        remote_name = full_path.name

    ensure_bucket_exists()

    try:
        with open(full_path, 'rb') as f:
            supabase.storage.from_(BUCKET_NAME).upload(
                path=remote_name,
                file=f,
                file_options={'content-type': _guess_mime(full_path)},
            )
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(remote_name)
        logger.info("Uploaded %s → %s", local_path, public_url)
        return public_url
    except Exception as exc:
        # If the file already exists remotely, that's fine — get the public URL
        err_str = str(exc).lower()
        if 'already exists' in err_str or 'duplicate' in err_str:
            public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(remote_name)
            return public_url
        logger.error("Failed to upload %s: %s", local_path, exc)
        return None


def _guess_mime(path: Path) -> str:
    """Return a basic MIME type based on file extension."""
    ext = path.suffix.lower()
    mime_map = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.mp4': 'video/mp4',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.txt': 'text/plain',
        '.csv': 'text/csv',
    }
    return mime_map.get(ext, 'application/octet-stream')

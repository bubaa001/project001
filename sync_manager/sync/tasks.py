"""
Core django-q2 task: process pending SyncRecords and push them to Supabase.

This is the heart of the offline-first sync.  It runs as a scheduled
django-q2 cron job every 60 seconds (only when connectivity is confirmed).
"""
import json
import logging
from typing import Any, Dict, List, Optional
from django.conf import settings
from django.db import models as dj_models
from ONLportal.supabase_client import supabase_service as supabase
from sync_manager.models import SyncRecord
from sync_manager.sync.file_uploader import upload_file
from sync_manager.sync.remote_schema import ensure_remote_schema

logger = logging.getLogger('sync_manager.tasks')

# Map Django model class names → Supabase REST endpoint table names
# (Supabase REST API exposes tables by their Postgres name)
MODEL_TO_TABLE: Dict[str, str] = {
    'User':                    'accounts_user',
    'AcademicClass':           'accounts_academicclass',
    'Module':                  'accounts_module',
    'ClassContent':            'accounts_classcontent',
    'ArchiveCategory':         'accounts_archivecategory',
    'ArchiveItem':             'accounts_archiveitem',
    'Quiz':                    'accounts_quiz',
    'Question':                'accounts_question',
    'Choice':                  'accounts_choice',
    'LibraryBook':             'accounts_librarybook',
    'InstructorProfile':       'accounts_instructorprofile',
    'StudentQuizSubmission':   'accounts_studentquizsubmission',
}

# Columns to strip from payloads before syncing (internal / auto-managed)
ALWAYS_STRIP_COLUMNS = set()  # hashed passwords are safe to sync over HTTPS

COLUMNS_TO_STRIP_BY_TABLE: Dict[str, set] = {
    'accounts_user': {'last_login'},
    'accounts_studentquizsubmission': set(),
}


def sync_pending_records() -> Dict[str, int]:
    """
    Main sync entry point called by django-q2.

    Processes up to SYNC_BATCH_SIZE pending SyncRecords:
      1. Upload any file content to Supabase Storage.
      2. Upsert (or delete) the row in the remote Postgres via REST API.
      3. Mark each record as 'synced' or 'failed'.

    Returns a summary dict: {'synced': N, 'failed': N, 'skipped': N}
    """
    batch_size = getattr(settings, 'SYNC_BATCH_SIZE', 50)
    max_retries = getattr(settings, 'SYNC_RETRY_MAX', 5)

    # Ensure remote tables exist (idempotent, fast after first run).
    # If this fails due to connectivity, we still try syncing individual
    # records — tables likely exist from a previous successful run.
    # Individual record failures are caught per-record below.
    try:
        ensure_remote_schema()
    except Exception:
        logger.warning("Schema check skipped — will attempt records anyway.")

    pending = SyncRecord.objects.filter(
        status='pending',
        retry_count__lt=max_retries,
    ).order_by('created_at')[:batch_size]

    if not pending:
        return {'synced': 0, 'failed': 0, 'skipped': 0}

    logger.info("Syncing %d pending records...", len(pending))

    synced = 0
    failed = 0
    skipped = 0

    for record in pending:
        try:
            _sync_one_record(record)
            record.mark_synced()
            synced += 1
        except Exception as exc:
            # Connectivity errors are expected offline — log as warning
            err_str = str(exc).lower()
            if any(kw in err_str for kw in ('name or service not known', 'getaddrinfo',
                                               'connection refused', 'timeout')):
                logger.warning("Sync deferred (offline) for %s", record)
            else:
                logger.error("Sync failed for %s: %s", record, exc)
            record.mark_failed(str(exc))
            failed += 1

    # Purge old successfully synced records to keep the table small
    _purge_old_synced()

    logger.info("Sync cycle complete: synced=%d failed=%d skipped=%d",
                synced, failed, skipped)
    return {'synced': synced, 'failed': failed, 'skipped': skipped}


def _sync_one_record(record: SyncRecord) -> None:
    """Push a single SyncRecord to Supabase."""
    table = record.table_name

    # 1. Upload any files first so we can substitute remote URLs
    payload = _upload_and_remap_files(record)

    if record.action == 'delete':
        _remote_delete(table, record.row_id)
    else:
        _remote_upsert(table, record.row_id, payload)


def _upload_and_remap_files(record: SyncRecord) -> dict:
    """
    Upload local files referenced in file_paths, and replace local
    paths in payload_json with remote public URLs.
    """
    payload = dict(record.payload_json)  # shallow copy
    file_paths: list = record.file_paths or []

    for local_path in file_paths:
        if not local_path:
            continue
        remote_url = upload_file(local_path)
        if remote_url:
            # Replace any occurrence of the local path with the remote URL in payload
            for key, value in payload.items():
                if isinstance(value, str) and local_path in value:
                    payload[key] = value.replace(local_path, remote_url)

    # Strip columns that should never be pushed
    strip_cols = COLUMNS_TO_STRIP_BY_TABLE.get(record.table_name, set()) | ALWAYS_STRIP_COLUMNS
    for col in strip_cols:
        payload.pop(col, None)

    # Add id explicitly for upsert
    payload['id'] = record.row_id

    # Ensure JSON fields are actually JSON, not string representations
    for key, value in payload.items():
        if isinstance(value, (list, dict)):
            payload[key] = json.dumps(value) if not isinstance(value, str) else value

    return payload


def _remote_upsert(table: str, row_id: int, payload: dict) -> None:
    """
    Upsert a row into the remote Supabase table via the REST API.

    Uses POST with Prefer: resolution=merge-duplicates header so that
    if the row already exists by PK (id), it's updated rather than
    erroring with a duplicate-key violation.
    """
    resp = supabase.table(table).upsert(
        payload,
        on_conflict='id',
    ).execute()

    if hasattr(resp, 'error') and resp.error:
        raise RuntimeError(f"UPSERT {table}#{row_id}: {resp.error}")
    logger.debug("Upserted %s#%d", table, row_id)


def _remote_delete(table: str, row_id: int) -> None:
    """Delete a row from the remote Supabase table by its local PK."""
    resp = supabase.table(table).delete().eq('id', row_id).execute()
    if hasattr(resp, 'error') and resp.error:
        raise RuntimeError(f"DELETE {table}#{row_id}: {resp.error}")
    logger.debug("Deleted %s#%d", table, row_id)


def _purge_old_synced() -> None:
    """Delete SyncRecords older than 24 hours that have already been synced."""
    from datetime import timedelta
    from django.utils import timezone
    cutoff = timezone.now() - timedelta(hours=24)
    SyncRecord.objects.filter(status='synced', created_at__lt=cutoff).delete()

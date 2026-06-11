"""
Django signals that auto-capture every model write into a SyncRecord (outbox).

When any tracked model is created, updated, or deleted, a corresponding
SyncRecord is created with status='pending'.  The django-q2 cron job then
picks these up on its next cycle (if online).

IMPORTANT: Some operations (like ManyToMany .add()/.remove()) do NOT fire
the model's post_save/post_delete signals.  Those are handled explicitly
in the views or via m2m_changed signals below.
"""
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, List

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver

from sync_manager.models import SyncRecord

logger = logging.getLogger('sync_manager.signals')

# ---------------------------------------------------------------------------
# Registry: for each model we track, map its class name to the remote
# table name and a list of FileField / ImageField attribute names.
# ---------------------------------------------------------------------------
TRACKED_MODELS: dict = {
    'User': {
        'table': 'accounts_user',
        'file_fields': [],
    },
    'AcademicClass': {
        'table': 'accounts_academicclass',
        'file_fields': [],
    },
    'Module': {
        'table': 'accounts_module',
        'file_fields': [],
    },
    'ClassContent': {
        'table': 'accounts_classcontent',
        'file_fields': ['file'],
    },
    'ArchiveCategory': {
        'table': 'accounts_archivecategory',
        'file_fields': [],
    },
    'ArchiveItem': {
        'table': 'accounts_archiveitem',
        'file_fields': ['cover_image'],
    },
    'Quiz': {
        'table': 'accounts_quiz',
        'file_fields': [],
    },
    'Question': {
        'table': 'accounts_question',
        'file_fields': [],
    },
    'Choice': {
        'table': 'accounts_choice',
        'file_fields': [],
    },
    'LibraryBook': {
        'table': 'accounts_librarybook',
        'file_fields': ['file', 'thumbnail'],
    },
    'InstructorProfile': {
        'table': 'accounts_instructorprofile',
        'file_fields': ['avatar'],
    },
    'StudentQuizSubmission': {
        'table': 'accounts_studentquizsubmission',
        'file_fields': [],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _model_to_dict(instance) -> dict:
    """Serialize a model instance to a JSON-safe dict, excluding Django internals."""
    data = {}
    for field in instance._meta.get_fields():
        if not field.concrete:
            continue
        value = getattr(instance, field.attname)
        data[field.column] = _serialize_value(value)
    return data


def _serialize_value(value):
    """Convert Python values to JSON-serializable primitives."""
    from django.db.models.fields.files import FieldFile

    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, 'pk'):  # ForeignKey
        return value.pk
    # FileField / ImageField — store the name (relative path), not the object
    if isinstance(value, FieldFile):
        try:
            return value.name if value else ''
        except Exception:
            return ''
    if isinstance(value, (list, dict)):
        return value
    return value


def _collect_file_paths(instance, file_fields: List[str]) -> List[str]:
    """Collect absolute file paths from FileField/ImageField fields."""
    paths = []
    for field_name in file_fields:
        field = getattr(instance, field_name, None)
        if field and hasattr(field, 'path'):
            paths.append(field.path)
    return paths


def create_sync_record(instance, action: str) -> Optional[SyncRecord]:
    """
    Create a SyncRecord for a model instance if it's a tracked model.

    Returns the SyncRecord or None if the model is not tracked.
    """
    model_name = instance.__class__.__name__
    config = TRACKED_MODELS.get(model_name)
    if not config:
        return None

    file_paths = _collect_file_paths(instance, config['file_fields'])
    payload = _model_to_dict(instance)

    record = SyncRecord.objects.create(
        table_name=config['table'],
        row_id=instance.pk,
        action=action,
        payload_json=payload,
        file_paths=file_paths,
    )
    logger.debug("SyncRecord created: %s", record)
    return record


# ---------------------------------------------------------------------------
# post_save  – fired on Model.save() (create + update)
# ---------------------------------------------------------------------------

def _make_post_save_handler(model_class):
    """Factory that returns a post_save handler for a specific model."""
    @receiver(post_save, sender=model_class)
    def handler(sender, instance, created, **kwargs):
        action = 'create' if created else 'update'
        create_sync_record(instance, action)
    return handler


# ---------------------------------------------------------------------------
# post_delete – fired on Model.delete()
# ---------------------------------------------------------------------------

def _make_post_delete_handler(model_class):
    """Factory that returns a post_delete handler for a specific model."""
    @receiver(post_delete, sender=model_class)
    def handler(sender, instance, **kwargs):
        create_sync_record(instance, 'delete')
    return handler


# ---------------------------------------------------------------------------
# m2m_changed – for AcademicClass.students (ManyToMany)
# ---------------------------------------------------------------------------

@receiver(m2m_changed, sender=None)
def handle_m2m_changes(sender, instance, action, pk_set, **kwargs):
    """
    Capture ManyToMany changes (e.g., student enrolls/unenrolls from a class).

    When students are added/removed from an AcademicClass, we re-sync the
    AcademicClass payload (which doesn't include m2m directly) AND create
    entries for the through-table rows.
    """
    model_name = instance.__class__.__name__
    if model_name != 'AcademicClass':
        return

    if action in ('post_add', 'post_remove', 'post_clear'):
        # Re-sync the AcademicClass itself (for any denormalized counts)
        create_sync_record(instance, 'update')

        # Sync through-table rows
        if action == 'post_add':
            for student_id in pk_set or []:
                SyncRecord.objects.create(
                    table_name='accounts_academicclass_students',
                    row_id=0,  # composite PK — we use the pair as identifier
                    action='create',
                    payload_json={
                        'academicclass_id': instance.pk,
                        'user_id': student_id,
                    },
                )
        elif action == 'post_remove':
            for student_id in pk_set or []:
                SyncRecord.objects.create(
                    table_name='accounts_academicclass_students',
                    row_id=0,
                    action='delete',
                    payload_json={
                        'academicclass_id': instance.pk,
                        'user_id': student_id,
                    },
                )


# ---------------------------------------------------------------------------
# Wire up all tracked models
# ---------------------------------------------------------------------------

_registered = False


def register_signals():
    """
    Called once on app ready() — connects all signal handlers.

    Guarded by a module-level flag so repeated imports / ready() calls
    are no-ops.
    """
    global _registered
    if _registered:
        return

    from accounts.models import (
        User, AcademicClass, Module, ClassContent,
        ArchiveCategory, ArchiveItem, Quiz, Question, Choice,
        LibraryBook, InstructorProfile, StudentQuizSubmission,
    )

    all_models = [
        User, AcademicClass, Module, ClassContent,
        ArchiveCategory, ArchiveItem, Quiz, Question, Choice,
        LibraryBook, InstructorProfile, StudentQuizSubmission,
    ]

    for model in all_models:
        _make_post_save_handler(model)
        _make_post_delete_handler(model)

    _registered = True
    logger.info("Sync signals registered for %d models.", len(all_models))

"""
Async sync triggers — importable from views to fire off an immediate
sync attempt after high-priority user actions (registration, book upload).
These are fire-and-forget; the django-q2 cluster handles execution.
"""
import logging
from django_q.tasks import async_task

logger = logging.getLogger('sync_manager.triggers')


def trigger_sync_after_action() -> None:
    """
    Queue an immediate sync cycle via django-q2.

    Call this from views after any user-facing write that should sync ASAP
    (e.g., new registration, book upload, quiz submission).

    This is fire-and-forget: the task runs in the django-q2 cluster at
    the next available worker slot.  If offline, the task will be retried
    by django-q2's built-in retry mechanism.
    """
    try:
        async_task('sync_manager.sync.tasks.sync_pending_records')
        logger.debug("Immediate sync task queued.")
    except Exception:
        pass  # qcluster not running — cron picks it up next cycle

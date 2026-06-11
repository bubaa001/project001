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
        async_task(
            'sync_manager.sync.tasks.sync_pending_records',
            hook=_sync_hook,
        )
        logger.debug("Immediate sync task queued.")
    except Exception:
        logger.debug("Could not queue async sync (django-q2 cluster may not be running).")
        # This is fine — the cron job will pick it up on the next cycle.


def _sync_hook(task) -> None:
    """Log the result of an async sync task."""
    if task.success:
        logger.info("Async sync completed: %s", task.result)
    else:
        logger.warning("Async sync failed: %s", task.result)

"""
django-q2 cron entry points called by the Q2_SCHEDULE config.

These are thin wrappers that:
  - check_connectivity()  → logs online/offline status
  - sync_all_pending()    → only invokes the sync task if online
"""
import logging
from sync_manager.sync.connectivity import is_online, clear_connectivity_cache
from sync_manager.sync.tasks import sync_pending_records

logger = logging.getLogger('sync_manager.scheduler')


def check_connectivity() -> dict:
    """
    Cron task — runs every 30 seconds.
    Logs connectivity status; clears cache so next sync cycle gets fresh state.
    """
    clear_connectivity_cache()
    online = is_online()
    logger.info("Connectivity: %s", "ONLINE" if online else "OFFLINE")
    return {'online': online}


def sync_all_pending() -> dict:
    """
    Cron task — runs every 60 seconds.
    Only invokes the real sync engine if Supabase is currently reachable.
    """
    if not is_online():
        logger.debug("Offline — skipping sync cycle.")
        return {'status': 'offline'}

    logger.info("Online — starting sync cycle.")
    result = sync_pending_records()
    return {'status': 'online', **result}

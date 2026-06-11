"""
Minimal connectivity check — makes a lightweight request to the Supabase
REST API and caches the result for a short TTL so we don't hammer the
network on every cron tick.
"""
import time
import logging
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('sync_manager.connectivity')

CONNECTIVITY_CACHE_KEY = 'sync_manager_online_status'


def is_online() -> bool:
    """Return True if Supabase is currently reachable.

    Uses Django's cache framework to avoid checking on every cron tick.
    Fallback: if no cache backend is configured, always re-check.
    """
    ttl = getattr(settings, 'SYNC_CONNECTIVITY_CACHE_TTL', 10)

    try:
        cached = cache.get(CONNECTIVITY_CACHE_KEY)
        if cached is not None:
            return cached
    except Exception:
        pass  # cache backend not available — re-check every time

    try:
        # Use a lightweight REST health-check endpoint.
        # The Supabase REST API returns a valid response for any table
        # request, so we use the built-in health endpoint pattern.
        import requests
        url = f"{settings.SUPABASE_URL}/rest/v1/"
        headers = {
            'apikey': settings.SUPABASE_KEY,
            'Authorization': f'Bearer {settings.SUPABASE_KEY}',
        }
        resp = requests.get(url, headers=headers, timeout=settings.SYNC_CONNECTIVITY_TIMEOUT)
        online = resp.status_code < 500
    except Exception:
        online = False

    try:
        cache.set(CONNECTIVITY_CACHE_KEY, online, ttl)
    except Exception:
        pass

    logger.debug("Connectivity check: %s", "ONLINE" if online else "OFFLINE")
    return online


def clear_connectivity_cache() -> None:
    """Force the next is_online() call to actually hit the network."""
    try:
        cache.delete(CONNECTIVITY_CACHE_KEY)
    except Exception:
        pass

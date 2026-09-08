# tria_engine/core/cache.py
#
# Small optional cache used by hot read endpoints (e.g. the subject
# /enrollment-counts aggregate).
#
#   * Redis when settings.REDIS_URL is configured (redis-py; lazily imported
#     so local dev without the package never breaks).
#   * Otherwise an in-process, thread-safe TTL dict — the app always works
#     out of the box in local dev without Redis.
#
# Values are JSON-encoded strings so a single code path serves both backends.

from __future__ import annotations

import json
import threading
import time

from .config import settings

_LOCK = threading.Lock()
_STORE: dict[str, tuple[float, str]] = {}

DEFAULT_TTL_SECONDS = 15

_redis_client = None


def _get_redis():
    """Lazily build the shared redis client (once)."""
    global _redis_client
    if _redis_client is None:
        import redis

        _redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def cache_get(key: str) -> str | None:
    """Return the cached JSON string for `key`, or None when missing/expired."""
    if not key:
        return None
    if settings.REDIS_URL:
        try:
            return _get_redis().get(key)
        except Exception:
            return None
    with _LOCK:
        entry = _STORE.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at < time.monotonic():
            _STORE.pop(key, None)
            return None
        return value


def cache_set(key: str, value: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    """Store `value` (already a JSON string) under `key` for ttl_seconds."""
    if not key:
        return
    if settings.REDIS_URL:
        try:
            _get_redis().set(key, value, ex=max(int(ttl_seconds), 1))
            return
        except Exception:
            return
    with _LOCK:
        _STORE[key] = (time.monotonic() + max(float(ttl_seconds), 0), value)


def cache_delete(key: str) -> None:
    """Drop `key` from whichever backend is active (no-op when absent)."""
    if not key:
        return
    if settings.REDIS_URL:
        try:
            _get_redis().delete(key)
            return
        except Exception:
            return
    with _LOCK:
        _STORE.pop(key, None)


def cache_get_json(key: str):
    """Convenience: cache_get + json.loads (None when missing/invalid)."""
    raw = cache_get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def cache_set_json(key: str, value, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    cache_set(key, json.dumps(value), ttl_seconds=ttl_seconds)


# Cache key for the per-study enrollment-counts aggregate (Task 3).
ENROLLMENT_COUNTS_CACHE_KEY = "ctms:subjects:enrollment-counts"
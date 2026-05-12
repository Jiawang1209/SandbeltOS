"""Tiny async Redis JSON cache with graceful degradation.

Used by the prediction service to memoize Prophet forecasts by
(region, indicator, horizon, as_of_day). When Redis is unreachable
(no daemon, network error, mis-configured URL) every call quietly
returns None / no-op so callers never have to special-case it.

Cache misses are normal — *failures* are logged at WARNING with the
underlying exception so an operator can spot a misconfigured deploy
without crashing the request path.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as redis_asyncio

from app.config import get_settings

logger = logging.getLogger(__name__)

# Cached client — created lazily so importing this module never opens a
# socket. None means "tried, failed, don't retry this process."
_client: redis_asyncio.Redis | None = None
_disabled: bool = False


def _client_or_none() -> redis_asyncio.Redis | None:
    global _client, _disabled
    if _disabled:
        return None
    if _client is not None:
        return _client
    try:
        _client = redis_asyncio.from_url(
            get_settings().redis_url, decode_responses=True
        )
        return _client
    except Exception as exc:  # noqa: BLE001
        logger.warning("redis client init failed, cache disabled: %s", exc)
        _disabled = True
        return None


async def get_json(key: str) -> Any | None:
    """Fetch JSON value at `key`. Returns None on miss or any error."""
    client = _client_or_none()
    if client is None:
        return None
    try:
        raw = await client.get(key)
    except Exception as exc:  # noqa: BLE001 — Redis offline is non-fatal
        logger.warning("cache get failed for %s: %s", key, exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("cache corrupt for %s: %s", key, exc)
        return None


async def set_json(key: str, value: Any, ttl_seconds: int = 1800) -> None:
    """Store JSON value with TTL. Silently drops on Redis failure."""
    client = _client_or_none()
    if client is None:
        return
    try:
        await client.set(key, json.dumps(value, default=str), ex=ttl_seconds)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache set failed for %s: %s", key, exc)

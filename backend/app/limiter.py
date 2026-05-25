"""Single slowapi Limiter instance shared between main.py and routers.

Lives in its own module so per-route decorators (`@limiter.limit(...)`)
in `app.api.v1.*` can import it without creating a circular dep with
`app.main` (which imports the routers).

Enabled flag respects `API_RATE_LIMIT`: when that env var is empty, the
limiter object still exists (so decorators don't crash) but enforcement
is off across the board — useful for `pytest -n auto` runs where rapid
parallel requests would otherwise hit 429.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

_settings = get_settings()

_default_limits: list[str] = [_settings.api_rate_limit] if _settings.api_rate_limit else []

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=_default_limits,
    enabled=bool(_settings.api_rate_limit),
)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import basemap, chat, ecological, gis, grid, prediction
from app.config import get_settings

settings = get_settings()

# ---------- Sentry ----------
# DSN absent → SDK never initializes, zero overhead. Traces sample rate
# stays at 0.0 by default; tune via SENTRY_TRACES_SAMPLE_RATE when you
# want performance spans (each costs ingest quota).
if settings.sentry_dsn:
    import sentry_sdk  # type: ignore[import-not-found]

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )

app = FastAPI(
    title="SandbeltOS API",
    version="0.1.0",
    description="三北防护林智慧生态决策支持系统",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Rate limiting (slowapi) ----------
# Global default limit applied via middleware so every route is covered
# without per-route decorators. Empty `api_rate_limit` disables — useful
# for tests where you don't want 429s on rapid `pytest -n auto` runs.
if settings.api_rate_limit:
    from slowapi import Limiter, _rate_limit_exceeded_handler  # type: ignore[import-not-found]
    from slowapi.errors import RateLimitExceeded  # type: ignore[import-not-found]
    from slowapi.middleware import SlowAPIMiddleware  # type: ignore[import-not-found]
    from slowapi.util import get_remote_address  # type: ignore[import-not-found]

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[settings.api_rate_limit],
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

# ---------- Prometheus metrics ----------
# Mounts GET /metrics with default HTTP request histograms + counters.
# /health and /metrics themselves are excluded so probe/scrape traffic
# doesn't pollute the per-route latency distributions.
try:
    from prometheus_fastapi_instrumentator import Instrumentator  # type: ignore[import-not-found]

    Instrumentator(
        excluded_handlers=["/metrics", "/health"],
    ).instrument(app).expose(app, include_in_schema=False, should_gzip=True)
except ImportError:
    # Observability deps are optional — lean test envs may skip them.
    pass

app.include_router(ecological.router, prefix="/api/v1/ecological", tags=["生态指标"])
app.include_router(gis.router, prefix="/api/v1/gis", tags=["GIS空间"])
app.include_router(grid.router, prefix="/api/v1/grid", tags=["像素热点"])
app.include_router(basemap.router, prefix="/api/v1/basemap", tags=["卫星底图"])
app.include_router(prediction.router, prefix="/api/v1/prediction", tags=["预测情景"])
app.include_router(chat.router, prefix="/api/v1", tags=["对话"])


@app.get("/health")
async def health(request: Request):  # noqa: ARG001 — request required by slowapi
    return {"status": "ok", "version": app.version}

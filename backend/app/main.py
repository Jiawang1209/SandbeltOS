from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import ecological, gis
from app.config import get_settings

settings = get_settings()

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

app.include_router(ecological.router, prefix="/api/v1/ecological", tags=["生态指标"])
app.include_router(gis.router, prefix="/api/v1/gis", tags=["GIS空间"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version}

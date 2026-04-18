from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import basemap, chat, ecological, gis, grid
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
app.include_router(grid.router, prefix="/api/v1/grid", tags=["像素热点"])
app.include_router(basemap.router, prefix="/api/v1/basemap", tags=["卫星底图"])
app.include_router(chat.router, prefix="/api/v1", tags=["对话"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version}

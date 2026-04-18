# syntax=docker/dockerfile:1.7

# =========================================================================
# SandbeltOS Backend (FastAPI + PostGIS + RAG)
# 运行时依赖：GDAL / PROJ / libpq；Python 3.11；大约 3-4 GB 镜像
# =========================================================================
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # HuggingFace 缓存统一到挂载卷里，避免容器重启重下 bge-m3 (~2GB)
    HF_HOME=/root/.cache/huggingface \
    TRANSFORMERS_CACHE=/root/.cache/huggingface \
    # geopandas / rasterio 运行时需要
    PROJ_LIB=/usr/share/proj \
    GDAL_DATA=/usr/share/gdal

# 系统依赖：
#   - build-essential + python-dev：某些 wheel 不完备时用于源码编译
#   - gdal-bin + libgdal-dev：rasterio/fiona/geopandas 必需
#   - libpq-dev：psycopg2/asyncpg 编译期依赖
#   - curl：容器内健康检查
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gdal-bin libgdal-dev \
        libpq-dev \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 分层：先装依赖，代码改动不会让 pip install 缓存失效
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# 应用代码（.dockerignore 已排除 __pycache__ / tests 结果等）
COPY backend/ /app/

# 预创建运行态目录（真实数据由 volume 覆盖）
RUN mkdir -p /app/rag/chroma_store /app/rag/docs /app/secrets

EXPOSE 8000

# --proxy-headers：放在 Nginx 后面时正确识别客户端 IP 与协议
# 不要用 --reload（生产）
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]

# SandbeltOS 部署指南

> 把三北防护林智慧生态决策支持系统部署到云服务器的完整操作手册。
> 适用：Ubuntu 22.04 / Debian 12 / 任何 x86_64 Linux，2c4g 起步，推荐 4c8g。

---

## 0. 一分钟总览

| 目标 | 推荐方案 | 复杂度 | 首次部署时长 |
|------|---------|-------|------------|
| 纯演示 / 原型 | **A：Docker Compose 单机全栈**（推荐） | ★★☆ | 30–60 min |
| 生产长期运行 | **B：systemd 原生部署 + 托管 DB** | ★★★★ | 2–4 h |
| 前端上 CDN | **C：Vercel 托管前端 + 服务器只跑后端** | ★★☆ | 1–2 h |

本指南主推 **方案 A**，方案 B/C 在文末给出差异点。

---

## 1. 打包清单：哪些东西必须带到服务器

### 1.1 ✅ 必须打包（代码 & 配置）

| 类别 | 内容 | 大小 | 打包方式 |
|------|------|------|---------|
| 后端代码 | `backend/app/`, `backend/rag/*.py`, `backend/scripts/`, `backend/sql/`, `requirements.txt`, `pytest.ini` | ~5 MB | Git 仓库 |
| 前端代码 | `frontend/src/`, `frontend/public/`, `package.json`, `package-lock.json`, `next.config.ts`, `tsconfig.json`, `postcss.config.mjs`, `eslint.config.mjs` | ~10 MB | Git 仓库 |
| 数据库 Schema | `backend/sql/init.sql` | < 1 MB | Git 仓库 |
| 环境模板 | `.env.example` | < 1 KB | Git 仓库 |
| 文档 | `README.md`, `PLAN.md`, `docs/` | ~1 MB | Git 仓库 |

### 1.2 ✅ 应该一起带（运行态数据）

这些**不进 Git**，但服务器首次启动需要——要么**从本地打 tar 上传**，要么**服务器首次启动时重新生成**。

| 类别 | 路径 | 大小 | 建议策略 |
|------|------|------|---------|
| 沙地矢量边界 | `data/boundaries/` | 几十 MB | **打包上传**（避免重新找源数据） |
| RAG 原始语料 PDF | `backend/rag/docs/` | 几十 MB–几百 MB | **打包上传**（重建需重跑下载脚本） |
| ChromaDB 向量库 | `backend/rag/chroma_store/` | 几百 MB | **打包上传**或服务器重跑 `ingest.py` |
| 离线 NDVI / ERA5 样本 | `data/sample/`, `data/rag_docs/` | 视数据量 | 按需 |
| 数据库初始种子 | `pg_dump` 导出 | 几十 MB–几百 MB | **强烈建议打包**（见 §5.2） |

### 1.3 ❌ 一定不要打包

| 内容 | 原因 | 处理方式 |
|------|------|---------|
| `.env` | 含密钥（LLM / DB 密码 / GEE key） | 服务器上单独创建（§3） |
| `secrets/gee-key.json` | Google 服务账号私钥 | `scp` 单独上传到服务器 `~/secrets/`，权限 `chmod 600` |
| `frontend/node_modules/` | ~500 MB，平台相关 | 服务器上 `npm ci` 重装 |
| `.venv/`, `venv/`, `__pycache__/` | 平台相关 | 服务器上重建 |
| `frontend/.next/` | 构建产物，需在服务器重新 build | 服务器上 `npm run build` |
| `backend/ml/models/*.pt/*.pkl` | 大模型权重，用镜像/挂载 | 挂载到容器或单独上传 |
| `frontend/test-results/`, `playwright-report/` | 本地测试产物 | — |

---

## 2. 云服务器前置准备

### 2.1 服务器规格

| 用途 | CPU | 内存 | 硬盘 | 带宽 | 备注 |
|------|-----|------|------|------|------|
| 演示 / 小团队 | 2 vCPU | 4 GB | 60 GB SSD | 3 Mbps | 够跑，但首次 `bge-reranker` 加载会吃满内存 |
| **推荐** | 4 vCPU | 8 GB | 100 GB SSD | 5 Mbps | RAG 流畅 |
| 满载生产 | 4 vCPU | 16 GB | 200 GB SSD | 10 Mbps | 留给 Prophet/LSTM/并发 RAG |

> **注意**：`FlagEmbedding` 的 `bge-m3` + `bge-reranker-v2-m3` 冷加载约占 2.5 GB RAM。低于 4 GB 容易 OOM。

### 2.2 一键装基础环境

```bash
# 以 root 或 sudo 用户执行
apt-get update && apt-get install -y \
    git curl wget ca-certificates gnupg lsb-release \
    build-essential ufw

# Docker + Docker Compose v2
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER  # 让当前用户免 sudo 用 docker；退出重登生效

# 防火墙：只开 22/80/443
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
```

### 2.3 域名与 DNS（可选但推荐）

在域名解析面板添加：

```
A    sandbelt.yourdomain.com    <服务器公网 IP>
A    api.sandbelt.yourdomain.com <服务器公网 IP>
```

---

## 3. 配置 `.env`（最关键的一步）

### 3.1 在项目根创建生产 `.env`

```bash
cp .env.example .env
vim .env
```

### 3.2 生产环境必改项

```ini
# === App ===
APP_ENV=production
CORS_ORIGINS=https://sandbelt.yourdomain.com

# === Database（Docker Compose 会起一个 postgres 服务，下面 host 用 postgres） ===
DATABASE_URL=postgresql+asyncpg://sandbelt:<强密码>@postgres:5432/sandbelt_db
DATABASE_URL_SYNC=postgresql://sandbelt:<强密码>@postgres:5432/sandbelt_db

# === Redis ===
REDIS_URL=redis://redis:6379/0

# === LLM（按你的实际服务商填） ===
LLM_BASE_URL=https://uni-api.cstcloud.cn/v1
LLM_API_KEY=<你的 key>
LLM_MODEL=qwen3:235b

# === GEE ===
GEE_SERVICE_ACCOUNT=your-sa@project.iam.gserviceaccount.com
GEE_KEY_FILE=/app/secrets/gee-key.json   # 容器内路径

# === CDS / ERA5 ===
CDS_KEY=<uid>:<key>
```

### 3.3 上传 GEE 密钥到服务器

```bash
# 本地
scp secrets/gee-key.json ubuntu@<服务器IP>:~/sandbelt-secrets/

# 服务器
chmod 600 ~/sandbelt-secrets/gee-key.json
```

---

## 4. 方案 A：Docker Compose 一键全栈（推荐）

### 4.1 目录结构（部署到服务器后）

```
/opt/sandbelt/
├── repo/                      # git clone 的项目
│   ├── backend/
│   ├── frontend/
│   └── docker-compose.yml     # 你新建的
├── secrets/
│   └── gee-key.json
├── data/                      # 持久化卷的宿主机挂载点
│   ├── postgres/
│   ├── chroma/
│   └── rag_docs/
└── .env                       # 生产 env
```

### 4.2 新建 `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# geopandas/rasterio 需要 GDAL 系统库
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gdal-bin libgdal-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/ /app/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

### 4.3 新建 `frontend/Dockerfile`

```dockerfile
# ---- builder ----
FROM node:20-alpine AS builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- runner ----
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/next.config.ts ./
EXPOSE 3000
CMD ["npm", "run", "start"]
```

### 4.4 根目录新建 `docker-compose.yml`

```yaml
services:
  postgres:
    image: postgis/postgis:16-3.4
    restart: unless-stopped
    environment:
      POSTGRES_DB: sandbelt_db
      POSTGRES_USER: sandbelt
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
      - ./backend/sql/init.sql:/docker-entrypoint-initdb.d/01_init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sandbelt -d sandbelt_db"]
      interval: 10s
      retries: 6

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - ./data/redis:/data

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    restart: unless-stopped
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - ./secrets:/app/secrets:ro
      - ./data/chroma:/app/rag/chroma_store
      - ./data/rag_docs:/app/rag/docs
    ports:
      - "127.0.0.1:8000:8000"   # 只绑 localhost，Nginx 反代

  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
    restart: unless-stopped
    environment:
      - NODE_ENV=production
    ports:
      - "127.0.0.1:3000:3000"
    depends_on:
      - backend
```

> **TimescaleDB 可选**：如不用时序超表功能，`postgis/postgis:16-3.4` 已够；要启用，换镜像 `timescale/timescaledb-ha:pg16` 并在 `init.sql` 加 `CREATE EXTENSION timescaledb;`。

### 4.5 启动

```bash
cd /opt/sandbelt/repo
docker compose --env-file ../.env up -d --build

# 看日志
docker compose logs -f backend
docker compose logs -f frontend

# 健康检查
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:3000
```

---

## 5. 数据初始化（服务器首次运行必做）

### 5.1 执行 Schema 扩展（如 init.sql 没有覆盖）

```bash
docker compose exec postgres psql -U sandbelt -d sandbelt_db -c \
    "CREATE EXTENSION IF NOT EXISTS postgis;"
# 如使用 TimescaleDB 镜像：
docker compose exec postgres psql -U sandbelt -d sandbelt_db -c \
    "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

### 5.2 迁移本地数据库（推荐：带着现成数据上线）

```bash
# 本地：导出
pg_dump -U sandbelt -d sandbelt_db -Fc -f sandbelt.dump

# 上传
scp sandbelt.dump ubuntu@<IP>:/tmp/

# 服务器：导入
docker compose cp /tmp/sandbelt.dump postgres:/tmp/
docker compose exec postgres pg_restore -U sandbelt -d sandbelt_db \
    --clean --if-exists /tmp/sandbelt.dump
```

### 5.3 上传 ChromaDB 向量库（或在服务器重建）

**方式一：打包上传（快）**

```bash
# 本地
tar czf chroma_store.tgz -C backend/rag chroma_store
scp chroma_store.tgz ubuntu@<IP>:/opt/sandbelt/

# 服务器
tar xzf chroma_store.tgz -C data/chroma --strip-components=1
docker compose restart backend
```

**方式二：服务器上重跑 ingest**（慢，首次下载 bge-m3 约 2 GB）

```bash
# 先把 PDF 放到 data/rag_docs/（挂载到容器 /app/rag/docs/）
docker compose exec backend python -m rag.ingest
```

### 5.4 补种子（如果库是空的）

```bash
docker compose exec backend python scripts/seed_region_polygons.py
docker compose exec backend python scripts/seed_accurate_sandy.py
# 如果 GEE 已配好：
docker compose exec backend python scripts/fetch_real_gee.py
```

---

## 6. Nginx + HTTPS 反向代理

### 6.1 装 Nginx + Certbot

```bash
apt-get install -y nginx certbot python3-certbot-nginx
```

### 6.2 `/etc/nginx/sites-available/sandbelt.conf`

```nginx
# 前端
server {
    listen 80;
    server_name sandbelt.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# 后端 API（SSE 流式聊天需要关闭缓冲）
server {
    listen 80;
    server_name api.sandbelt.yourdomain.com;

    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # RAG 流式回答（SSE）
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        chunked_transfer_encoding on;
    }
}
```

### 6.3 启用 + 签证书

```bash
ln -s /etc/nginx/sites-available/sandbelt.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

certbot --nginx -d sandbelt.yourdomain.com -d api.sandbelt.yourdomain.com
# 自动续期测试
certbot renew --dry-run
```

### 6.4 让前端知道后端地址

前端代码里调用 API 的基址（例如 `fetch("/api/...")`）需要指向 `api.sandbelt.yourdomain.com`。如果是同域 `/api/` 代理，把前端 Nginx 多加一条：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    # ...（同上）
}
```

---

## 7. 备份与日常运维

### 7.1 自动备份数据库

```bash
# /opt/sandbelt/backup.sh
#!/bin/bash
set -e
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p /opt/sandbelt/backups
cd /opt/sandbelt/repo
docker compose exec -T postgres pg_dump -U sandbelt -d sandbelt_db -Fc \
    > /opt/sandbelt/backups/sandbelt-${TS}.dump
# 保留 14 天
find /opt/sandbelt/backups -name "*.dump" -mtime +14 -delete
```

```bash
chmod +x /opt/sandbelt/backup.sh
# crontab -e
0 3 * * * /opt/sandbelt/backup.sh >> /opt/sandbelt/backups/backup.log 2>&1
```

### 7.2 日志轮转

Docker 默认日志不轮转，`/etc/docker/daemon.json`：

```json
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "50m", "max-file": "5" }
}
```

```bash
systemctl restart docker
```

### 7.3 更新部署

```bash
cd /opt/sandbelt/repo
git pull
docker compose --env-file ../.env up -d --build
```

### 7.4 常用监控命令

```bash
docker compose ps                      # 容器状态
docker stats --no-stream               # CPU/内存
docker compose logs --tail=200 backend # 后端日志
docker compose exec postgres psql -U sandbelt -d sandbelt_db -c "SELECT pg_size_pretty(pg_database_size('sandbelt_db'));"
du -sh /opt/sandbelt/data/*            # 数据卷大小
```

---

## 8. 方案 B：systemd 原生部署（不用 Docker）

核心差异：

1. 服务器上复刻本地 conda/venv 环境（见 `PLAN.md` 环境搭建脚本）
2. PostgreSQL / Redis 走 `apt` 安装或用云厂商托管（RDS/阿里云 RDS）
3. 为 backend、frontend 各写一份 systemd unit：

```ini
# /etc/systemd/system/sandbelt-backend.service
[Unit]
Description=SandbeltOS Backend (FastAPI)
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=sandbelt
WorkingDirectory=/opt/sandbelt/repo/backend
EnvironmentFile=/opt/sandbelt/.env
ExecStart=/opt/sandbelt/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/sandbelt-frontend.service
[Unit]
Description=SandbeltOS Frontend (Next.js)
After=network.target sandbelt-backend.service

[Service]
Type=simple
User=sandbelt
WorkingDirectory=/opt/sandbelt/repo/frontend
Environment=NODE_ENV=production
ExecStart=/usr/bin/npm run start
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now sandbelt-backend sandbelt-frontend
```

**适合场景**：服务器资源紧张（省去 Docker overhead）、需要直接在宿主机调试、已有成熟 systemd 运维习惯。

---

## 9. 方案 C：前端 Vercel + 后端服务器

1. 把 `frontend/` 推到单独的 GitHub 仓库（或用 monorepo + rootDirectory）
2. Vercel 导入，设置环境变量 `NEXT_PUBLIC_API_BASE=https://api.sandbelt.yourdomain.com`
3. 服务器只跑 backend + postgres + redis（用方案 A 的 compose 删掉 frontend service）
4. Nginx 只反代 `api.sandbelt.yourdomain.com`
5. 后端 `CORS_ORIGINS=https://<你的-vercel-域名>`

**优点**：前端走 Vercel 全球 CDN；**代价**：多一个平台，前后端拆域名。

---

## 10. 常见问题

| 症状 | 排查 |
|------|------|
| 后端启动卡在 "Loading bge-m3" | 首次会下载 2 GB 模型，等 5–15 min；缓存后秒启 |
| `chromadb` 报 `SQLITE_CANTOPEN` | 容器内 `chroma_persist_dir` 路径没挂载，检查 §4.4 的 volumes |
| 前端打不通 `/api/*` | Nginx 没加 `/api/` location，或 `CORS_ORIGINS` 没包含前端域名 |
| SSE 聊天几秒就断 | Nginx 没加 `proxy_buffering off` 和 `proxy_read_timeout 300s` |
| GEE `Permission denied` | `gee-key.json` 没挂载 / 路径不对 / 服务账号未加入 GEE 项目白名单 |
| Postgres 容器起不来，报 "initdb: directory not empty" | 旧的 `data/postgres/` 没清；改名或删除后重启 |
| 内存爆 | `docker stats` 看谁爆；bge-reranker 可按需改 `RAG_TOP_K_RERANK=3` 降负载 |
| `docker compose` 命令找不到 | 老版 Docker 用 `docker-compose`（带连字符）；或升级 Docker |

---

## 11. 部署前 Checklist

- [ ] 本地能跑通前后端（`/health` 返回 ok，前端能渲染）
- [ ] `.env.example` 里所有 key 都在生产 `.env` 里有值
- [ ] `secrets/gee-key.json` 已上传到服务器且权限 600
- [ ] 域名 DNS 已解析到服务器 IP
- [ ] `data/postgres/`, `data/chroma/`, `data/rag_docs/` 宿主机目录已创建
- [ ] `backend/sql/init.sql` 在 postgres 首次启动时被执行（看日志确认）
- [ ] `pg_dump` 备份从本地迁移到服务器（或接受服务器从空库开始）
- [ ] Nginx + Certbot 通过 HTTPS 能访问
- [ ] `CORS_ORIGINS` 配成 HTTPS 域名
- [ ] 定时备份 crontab 已加
- [ ] 防火墙只开 22/80/443

---

*维护：SandbeltOS 团队 · 最后更新：2026-04-18*

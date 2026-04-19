# SandbeltOS · Docker 部署完全手册

> 从零到跑起来的一条龙操作指南。照着从上往下做即可，**不需要来回跳章节**。
> 目标环境：Ubuntu 22.04 LTS · 4 vCPU / 16 GB RAM / 100 GB SSD · 国内云服务器（阿里云/腾讯云/华为云等）。

---

## 目录

1. [架构总览](#1-架构总览)
2. [前置准备](#2-前置准备)
3. [一次性安装 Docker](#3-一次性安装-docker)
4. [拉代码 & 建目录](#4-拉代码--建目录)
5. [配置 `.env`（**最关键**）](#5-配置-env最关键)
6. [上传密钥](#6-上传密钥)
7. [首次构建 & 启动](#7-首次构建--启动)
8. [数据迁移（从本地搬数据到服务器）](#8-数据迁移从本地搬数据到服务器)
9. [访问应用](#9-访问应用)
10. [日常运维](#10-日常运维)
11. [关键注意事项 & 踩坑集锦](#11-关键注意事项--踩坑集锦)
12. [常见问题排查](#12-常见问题排查)
13. [附录 A · Nginx + HTTPS 配置](#附录-a--nginx--https-配置)
14. [附录 B · 从零初始化一个空库](#附录-b--从零初始化一个空库)

---

## 1. 架构总览

```
                 ┌──────────────────────────────────────────────┐
                 │              Docker Compose Network           │
                 │                                              │
  浏览器 ──▶  frontend:3000 ──┐                                 │
                 │            │ API                             │
                 │            ▼                                 │
  浏览器 ──▶  backend:8000 ──┬──▶  postgres:5432 (PostGIS+TSDB) │
                 │            │                                 │
                 │            ├──▶  redis:6379                  │
                 │            │                                 │
                 │            └──▶  ChromaDB (本地文件 volume)   │
                 └──────────────────────────────────────────────┘
```

**服务构成**（`docker-compose.yml` 里定义的 4 个容器）：

| 服务 | 镜像 | 端口 | 用途 |
|------|------|------|------|
| `postgres` | `timescale/timescaledb-ha:pg16` | 5432（仅容器网内）| 关系库 + 时序 + 空间 |
| `redis` | `redis:7-alpine` | 6379（仅容器网内）| 缓存 |
| `backend` | 本地构建（`backend/Dockerfile`） | 宿主 `8000` | FastAPI |
| `frontend` | 本地构建（`frontend/Dockerfile`） | 宿主 `3000` | Next.js |

**持久化卷**（宿主机 `./data/` 下）：

| 宿主路径 | 容器路径 | 内容 | 大小量级 |
|---------|---------|------|---------|
| `data/postgres/` | `/home/postgres/pgdata/data` | 整个数据库 | 几十 MB – 几 GB |
| `data/redis/` | `/data` | AOF 持久化 | < 100 MB |
| `data/chroma/` | `/app/rag/chroma_store` | 向量库 | 几百 MB |
| `data/rag_docs/` | `/app/rag/docs` | RAG 原始 PDF | 几十到几百 MB |
| `data/hf_cache/` | `/root/.cache/huggingface` | bge-m3 / bge-reranker 权重 | ~2.5 GB |
| `secrets/` | `/app/secrets` (ro) | GEE service account key | < 10 KB |

---

## 2. 前置准备

### 2.1 需要的信息

手上准备好以下东西（全部**在服务器外**准备）：

- [ ] 服务器的 **公网 IP** 和 SSH 用户名（这里以 `ubuntu@<IP>` 举例）
- [ ] 你的 **GitHub 仓库地址**（或项目 tar 包）
- [ ] **GEE Service Account JSON**（`secrets/gee-key.json`）
- [ ] **LLM API Key**（默认 CSTCloud uni-api；或换成任何 OpenAI-compatible 的）
- [ ] **CDS API Key**（可选，如果不跑 ERA5 采集可留空）
- [ ] 本地已有一份能跑的 **PostgreSQL 数据库** 和 **ChromaDB 目录**（用来迁移）

### 2.2 服务器前置

```bash
ssh ubuntu@<IP>
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ufw vim

# 防火墙：只开 SSH + HTTP + HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
# 演示阶段用 IP:端口直连时，也放通 3000 / 8000
sudo ufw allow 3000/tcp
sudo ufw allow 8000/tcp
sudo ufw --force enable
sudo ufw status
```

> **重要**：如果云厂商还有"安全组/网络 ACL"，防火墙放通了还不够，**必须在云厂商控制台也放通对应端口**，否则外网访问不到。

---

## 3. 一次性安装 Docker

```bash
# 官方一键脚本
curl -fsSL https://get.docker.com | sudo sh # 失效

# 2. 安装依赖
sudo apt update
sudo apt install ca-certificates curl gnupg

# 3. 添加 Docker 官方 GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 4. 添加仓库
echo \
  "deb [arch=$(dpkg --print-architecture) \
  signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 5. 安装最新版
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 创建ly的实例
sudo useradd -m -d /home/data/student/ly -s /bin/bash -k /etc/skel ly

#  新建 docker 组
sudo groupadd docker

# 让当前用户免 sudo 用 docker（退出重连生效）
sudo usermod -aG docker ly

# 重启 docker 服务
sudo systemctl restart docker
# 让当前 shell 临时刷新组身份
newgrp docker

exit
ssh ubuntu@<IP>

# 验证
docker --version 
# Docker version 29.4.0, build 9d7ad9f
docker compose version
# Docker Compose version v5.1.3
docker ps   # 不报 permission denied 就 OK



```

### 3.1 国内镜像加速（强烈推荐）

```bash
sudo tee /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "5"
  }
}
EOF
sudo systemctl restart docker
```

---

## 4. 拉代码 & 建目录

```bash
sudo mkdir -p /opt/sandbelt
sudo chown $USER:$USER /opt/sandbelt
cd /opt/sandbelt

# 克隆项目（替换成你的仓库地址）
git clone https://github.com/Jiawang1209/SandbeltOS.git
cd SandbeltOS

# 建宿主机挂载目录
mkdir -p secrets \
         data/postgres \
         data/redis \
         data/chroma \
         data/rag_docs \
         data/hf_cache
```

> 目录树此时应为：
> ```
> /opt/sandbelt/SandbeltOS/
> ├── .env.example
> ├── docker-compose.yml
> ├── backend/Dockerfile
> ├── frontend/Dockerfile
> ├── secrets/
> └── data/
>     ├── postgres/
>     ├── redis/
>     ├── chroma/
>     ├── rag_docs/
>     └── hf_cache/
> ```

---

## 5. 配置 `.env`（**最关键**）

```bash
cd /opt/sandbelt/SandbeltOS/
cp .env.example .env
vim .env
```

**以下字段必须根据生产环境修改**：

```ini
# === App ===
APP_ENV=production
# 关键：这里是前端访问的地址，CORS 必须允许。
# IP 直连模式：用服务器公网 IP；Nginx 反代模式：用你的域名
CORS_ORIGINS=http://<服务器IP>:3000
# 如果你要用域名 + HTTPS，改成：
# CORS_ORIGINS=https://sandbelt.yourdomain.com

# === PostgreSQL（Compose 内部网络，host 一定要写 `postgres`） ===
POSTGRES_DB=sandbelt_db
POSTGRES_USER=sandbelt
POSTGRES_PASSWORD=<生成一个 20 位强密码>
# 下面这两行实际被 docker-compose.yml 覆盖，保留给非 Compose 运行用
DATABASE_URL=postgresql+asyncpg://sandbelt:${POSTGRES_PASSWORD}@postgres:5432/sandbelt_db
DATABASE_URL_SYNC=postgresql://sandbelt:${POSTGRES_PASSWORD}@postgres:5432/sandbelt_db

# === Redis ===
REDIS_URL=redis://redis:6379/0

# === GEE ===
GEE_PROJECT=ee-yueliu19921209
GEE_SERVICE_ACCOUNT=your-sa@project.iam.gserviceaccount.com
GEE_KEY_FILE=/app/secrets/gee-key.json   # 容器内路径，别改

# === CDS / ERA5 ===
CDS_URL=https://cds.climate.copernicus.eu/api
CDS_KEY=<uid>:<key>

# === LLM ===
LLM_BASE_URL=https://uni-api.cstcloud.cn/v1
LLM_API_KEY=<你的 key>
LLM_MODEL=qwen3:235b
LLM_MAX_TOKENS=2048

# === RAG ===
RAG_EMBEDDER=BAAI/bge-m3
RAG_RERANKER=BAAI/bge-reranker-v2-m3
RAG_TOP_K_RETRIEVE=20
RAG_TOP_K_RERANK=5
RAG_CHUNK_SIZE=800
RAG_CHUNK_OVERLAP=100

# === 前端构建期 API 基址 ===
# ⚠️ 这里写什么，浏览器访问时前端就去敲什么。
# IP 直连：http://<服务器IP>:8000
# Nginx 同域：留空 "" 即可（走相对路径 /api/...）
# 域名分开：https://api.sandbelt.yourdomain.com
NEXT_PUBLIC_API_URL=http://<服务器IP>:8000

# === 端口映射（默认即可） ===
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

> **密码生成**：`openssl rand -base64 24` 一条命令搞定。

---

## 6. 上传密钥

在**本地**机器上执行（不是服务器）：

```bash
# 假设你本地项目在 ~/Desktop/SandbeltOS/
scp ~/Desktop/SandbeltOS/secrets/gee-key.json \
    ubuntu@<IP>:/opt/sandbelt/SandbeltOS/secrets/

# 回到服务器收紧权限
ssh ubuntu@<IP>
chmod 600 /opt/sandbelt/SandbeltOS/secrets/gee-key.json
ls -la /opt/sandbelt/SandbeltOS/secrets/   # 应该显示 -rw-------
```

---

## 7. 首次构建 & 启动

```bash
cd /opt/sandbelt/repo
docker compose up -d --build
```

首次构建时长参考（100 Mbps 服务器下行 + 已加镜像加速）：

| 步骤 | 耗时 |
|------|------|
| 拉取基础镜像（python:3.11-slim, node:20, timescale, redis, alpine） | 1–3 min |
| backend `pip install`（含 PyTorch） | 5–8 min |
| frontend `npm ci + build` | 2–4 min |
| **总计** | **约 10–15 min** |

**实时跟日志**：

```bash
docker compose logs -f
# 或者分开看：
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
```

**看到这些就算成功**：

- `postgres`: `database system is ready to accept connections`
- `backend`: `Uvicorn running on http://0.0.0.0:8000`
- `frontend`: `▲ Next.js 16.x ready in ...`

**健康检查**：

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0"}

curl -I http://localhost:3000
# HTTP/1.1 200 OK
```

---

## 8. 数据迁移（从本地搬数据到服务器）

### 8.1 迁移数据库

**本地**：

```bash
# 在本地项目根
pg_dump -U sandbelt -d sandbelt_db -Fc -f sandbelt.dump

# 上传（约几十 MB，1 Mbps 入站不限速时快得多）
scp sandbelt.dump ubuntu@<IP>:/tmp/
```

**服务器**：

```bash
cd /opt/sandbelt/repo

# 把 dump 丢进 postgres 容器
docker compose cp /tmp/sandbelt.dump postgres:/tmp/

# 恢复（--clean 会先清空同名对象，init.sql 建的空表会被覆盖）
docker compose exec postgres pg_restore \
    -U sandbelt -d sandbelt_db \
    --clean --if-exists --no-owner --no-privileges \
    /tmp/sandbelt.dump

# 验证
docker compose exec postgres psql -U sandbelt -d sandbelt_db -c \
    "SELECT count(*) AS regions FROM regions; \
     SELECT count(*) AS eco_rows FROM eco_indicators;"
```

### 8.2 迁移 ChromaDB 向量库

**本地**：

```bash
tar czf chroma_store.tgz -C backend/rag chroma_store
scp chroma_store.tgz ubuntu@<IP>:/tmp/
```

**服务器**：

```bash
cd /opt/sandbelt/repo
# 停 backend 再改动挂载卷数据
docker compose stop backend

# 解压到宿主机卷路径
sudo rm -rf data/chroma/*
sudo tar xzf /tmp/chroma_store.tgz -C data/chroma --strip-components=1
sudo chown -R 0:0 data/chroma   # 容器里 root:root 读写

docker compose start backend
docker compose logs -f backend   # 确认加载 chroma 无报错
```

### 8.3 迁移 RAG 原始 PDF（可选）

```bash
# 本地
tar czf rag_docs.tgz -C backend/rag docs

# 服务器
scp rag_docs.tgz ubuntu@<IP>:/tmp/
ssh ubuntu@<IP>
cd /opt/sandbelt/repo
sudo tar xzf /tmp/rag_docs.tgz -C data/rag_docs --strip-components=1
```

> 如果你只是演示，**ChromaDB 一样搬过来就够**，原始 PDF 可以不传。

---

## 9. 访问应用

### 9.1 模式 A · IP 直连（演示最快）

前提：`.env` 里 `NEXT_PUBLIC_API_URL=http://<IP>:8000` + `CORS_ORIGINS=http://<IP>:3000`。

```
浏览器打开：http://<服务器IP>:3000
```

> 浏览器会有 "Not Secure" 标记（HTTP 无证书），内部演示没问题。

### 9.2 模式 B · 域名 + HTTPS（正式）

详见 [附录 A · Nginx + HTTPS 配置](#附录-a--nginx--https-配置)。

配完以后 `.env` 改两处重新 build frontend：

```ini
CORS_ORIGINS=https://sandbelt.yourdomain.com
NEXT_PUBLIC_API_URL=https://sandbelt.yourdomain.com   # 同域，走相对 /api
```

```bash
docker compose up -d --build frontend backend
```

---

## 10. 日常运维

### 10.1 更新部署（改了代码 / `.env` 之后）

```bash
cd /opt/sandbelt/repo
git pull
docker compose up -d --build
```

只动前端代码：

```bash
docker compose up -d --build frontend
```

只改 `.env`（不需要重 build）：

```bash
docker compose up -d
```

改了 `NEXT_PUBLIC_API_URL`：**必须重 build frontend**，因为它 inline 在 bundle 里。

```bash
docker compose build --no-cache frontend
docker compose up -d
```

### 10.2 看日志

```bash
docker compose logs -f backend             # 实时
docker compose logs --tail=200 backend     # 最后 200 行
docker compose logs --since 30m backend    # 最近 30 分钟
```

### 10.3 进容器排查

```bash
# 进 backend shell
docker compose exec backend bash

# 进 postgres shell
docker compose exec postgres psql -U sandbelt -d sandbelt_db

# 跑一次性 Python 脚本（例如重新 ingest RAG）
docker compose exec backend python -m rag.ingest
```

### 10.4 重启单个服务

```bash
docker compose restart backend
docker compose restart frontend
```

### 10.5 停机 / 清理

```bash
docker compose stop              # 温柔停，数据保留
docker compose down              # 停 + 删容器，volume 保留
docker compose down -v           # ⚠️ 同时删 volume（数据全没！）
docker system prune -a -f        # 清理无用镜像（谨慎）
```

### 10.6 自动备份

```bash
# /opt/sandbelt/backup.sh
#!/bin/bash
set -e
cd /opt/sandbelt/repo
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p /opt/sandbelt/backups
docker compose exec -T postgres pg_dump -U sandbelt -d sandbelt_db -Fc \
    > /opt/sandbelt/backups/sandbelt-${TS}.dump
# 保留 14 天
find /opt/sandbelt/backups -name "*.dump" -mtime +14 -delete
```

```bash
chmod +x /opt/sandbelt/backup.sh
sudo crontab -e   # 加一行：
0 3 * * * /opt/sandbelt/backup.sh >> /opt/sandbelt/backups/backup.log 2>&1
```

---

## 11. 关键注意事项 & 踩坑集锦

### ⚠️ 1. `NEXT_PUBLIC_API_URL` 是 build-time 变量

**错误症状**：浏览器打开前端页面，所有 API 请求打到 `http://localhost:8000`，看 DevTools 报 `ERR_CONNECTION_REFUSED` 或 CORS 错误。

**原因**：`NEXT_PUBLIC_*` 开头的环境变量会在 `npm run build` 时被 inline 到 JS bundle 里。运行时改 `.env` **不生效**。

**解决**：每次改这个值，都要 **重新 build frontend**：

```bash
docker compose build --no-cache frontend && docker compose up -d frontend
```

### ⚠️ 2. `CORS_ORIGINS` 必须和浏览器访问地址完全一致

| 浏览器地址 | `CORS_ORIGINS` 必须是 |
|---|---|
| `http://1.2.3.4:3000` | `http://1.2.3.4:3000` |
| `https://sandbelt.domain.com` | `https://sandbelt.domain.com` |
| 两个都要支持 | `http://1.2.3.4:3000,https://sandbelt.domain.com`（**逗号分隔，无空格**） |

**协议、端口、斜杠**都要一致。多一个斜杠都会 CORS 报错。

### ⚠️ 3. 首次启动 backend 会 "卡" 5–10 分钟

**原因**：`FlagEmbedding` 首次加载 `bge-m3`（~2 GB）和 `bge-reranker-v2-m3`（~1.1 GB），从 HuggingFace 下载。

**观察**：`docker compose logs -f backend` 能看到 `Downloading ...` 进度。

**加速**（国内服务器）：设置 HuggingFace 镜像。在 `.env` 里加：

```ini
HF_ENDPOINT=https://hf-mirror.com
```

然后在 `backend/Dockerfile` 的 `ENV` 里加一行 `ENV HF_ENDPOINT=https://hf-mirror.com`（或者在 `docker-compose.yml` 的 backend 服务 `environment:` 段加），重新 build。

**缓存持久**：模型缓存在 `./data/hf_cache`，容器重启**秒起**，不会重下。

### ⚠️ 4. ChromaDB `SQLITE_CANTOPEN` 错误

**症状**：backend 启动报 `sqlite3.OperationalError: unable to open database file`。

**原因**：向量库路径没挂对，或者权限不对。

**排查**：

```bash
docker compose exec backend ls -la /app/rag/chroma_store
# 应能看到 chroma.sqlite3 文件
# 权限应该是 root 可读写（容器里默认 root 用户）
```

**修复**：

```bash
sudo chown -R 0:0 data/chroma
docker compose restart backend
```

### ⚠️ 5. `docker compose` vs `docker-compose`

**新版**（Docker 20.10+）：`docker compose`（有空格，是子命令）
**老版**（独立安装）：`docker-compose`（有连字符）

本指南全部用新版。如果你服务器是老版，替换所有命令即可，行为等价。

### ⚠️ 6. postgres volume 目录**不能预建子目录**

**错误症状**：`postgres` 容器起不来，报 `initdb: directory "/home/postgres/pgdata/data" exists but is not empty`。

**原因**：首次启动前你手动在 `data/postgres/` 下建了东西。

**修复**：

```bash
docker compose down
sudo rm -rf data/postgres/*    # 清空但保留目录
docker compose up -d
```

### ⚠️ 7. TimescaleDB 镜像的数据目录在 `/home/postgres/pgdata/data`

不是标准的 `/var/lib/postgresql/data`。`docker-compose.yml` 里已经配好，不用改。

### ⚠️ 8. SSE 流式聊天断开

**症状**：RAG 聊天开始几秒后断，或者所有内容一次性吐出（没有打字机效果）。

**原因**：Nginx 反代默认启用缓冲。

**修复**：见 [附录 A](#附录-a--nginx--https-配置)，`proxy_buffering off` + `proxy_read_timeout 300s`。

### ⚠️ 9. 云厂商"安全组"是独立的一层

防火墙（ufw）放通了还不够。**阿里云/腾讯云控制台**的"安全组规则"也要放通 22/80/443/3000/8000，否则外网访问不到。

### ⚠️ 10. 第一次访问 `/docs` 或 `/openapi.json` 慢

FastAPI 首次生成 OpenAPI schema 要几秒，之后缓存。不是 bug。

---

## 12. 常见问题排查

| 症状 | 原因 & 解决 |
|------|-----|
| `docker compose up` 卡在 `Building backend`，很久没反应 | 正在下载 PyTorch wheel（~800 MB）。加镜像加速；或在 `requirements.txt` 里指定 `torch==x.x.x+cpu` 用 CPU 版（小 4 倍） |
| `frontend build` 失败，`Error: Cannot find module 'xxx'` | 本地 `package-lock.json` 没提交。本地跑 `npm i` 并 commit lock 文件后重新部署 |
| 打开 `http://IP:3000` 白屏，F12 看到 `Refused to connect to http://localhost:8000` | `NEXT_PUBLIC_API_URL` 没传或没生效。按 §11-1 重 build frontend |
| 前端能访问，但所有 API 请求 CORS 报错 | `.env` 里 `CORS_ORIGINS` 和浏览器地址不一致（见 §11-2） |
| backend 日志反复出现 `could not connect to server` | postgres 还没就绪。compose 的 `depends_on.condition: service_healthy` 应该等好；如果频繁，加大 `healthcheck.retries` |
| RAG 问答返回 500，报 `openai.APIConnectionError` | `LLM_BASE_URL` / `LLM_API_KEY` 没填或错了。试 `docker compose exec backend curl -v $LLM_BASE_URL/models -H "Authorization: Bearer $LLM_API_KEY"` |
| GEE 调用报 `PERMISSION_DENIED` | `gee-key.json` 没挂载 / 路径错 / 服务账号没加入 GEE 项目白名单 |
| 服务器内存打满 | `docker stats` 看元凶。多数是 backend 的 reranker；可调 `.env` 里 `RAG_TOP_K_RERANK=3` 降负载 |
| 磁盘满了 | `docker system df` 看；`docker compose down && docker system prune -a -f` 清理无用镜像；看 `data/postgres` 增长（时序表膨胀） |

---

## 附录 A · Nginx + HTTPS 配置

### A.1 让 frontend/backend 只监听 localhost

编辑 `docker-compose.yml`，把 `ports` 改成只绑 `127.0.0.1`：

```yaml
backend:
  ports:
    - "127.0.0.1:8000:8000"
frontend:
  ports:
    - "127.0.0.1:3000:3000"
```

```bash
docker compose up -d
```

### A.2 装 Nginx + Certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### A.3 `/etc/nginx/sites-available/sandbelt.conf`

```nginx
server {
    listen 80;
    server_name sandbelt.yourdomain.com;

    # 前端
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

    # 后端 API（同域 /api/ 转发，并保证 SSE 流式）
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE：关键三行
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        chunked_transfer_encoding on;
    }

    # gzip / brotli
    gzip on;
    gzip_types application/json application/javascript text/css
               application/geo+json image/svg+xml;
    gzip_min_length 1024;

    client_max_body_size 50m;
}
```

### A.4 启用 + 签证书

```bash
sudo ln -s /etc/nginx/sites-available/sandbelt.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

sudo certbot --nginx -d sandbelt.yourdomain.com
# 自动续期测试
sudo certbot renew --dry-run
```

### A.5 改 `.env` 并重 build frontend

```ini
CORS_ORIGINS=https://sandbelt.yourdomain.com
NEXT_PUBLIC_API_URL=https://sandbelt.yourdomain.com   # 同域
```

```bash
docker compose build --no-cache frontend && docker compose up -d
```

---

## 附录 B · 从零初始化一个空库

如果你**没有本地数据可迁移**，走完 §7 启动后，`init.sql` 已经建好了表结构（空）。用仓库自带的种子脚本填充：

```bash
cd /opt/sandbelt/repo

# 导入沙地矢量边界
docker compose exec backend python scripts/seed_region_polygons.py
docker compose exec backend python scripts/seed_accurate_sandy.py

# 从 GEE 拉遥感数据（需要 GEE 账号可用）
docker compose exec backend python scripts/fetch_real_gee.py

# 算风险指标
docker compose exec backend python scripts/compute_risk.py

# RAG：把 data/rag_docs/ 里的 PDF 切片入 Chroma
#（先把 PDF 拷进 /opt/sandbelt/repo/data/rag_docs/）
docker compose exec backend python -m rag.ingest
```

验证：

```bash
docker compose exec postgres psql -U sandbelt -d sandbelt_db <<'SQL'
SELECT 'regions' AS t, count(*) FROM regions UNION ALL
SELECT 'eco_indicators', count(*) FROM eco_indicators UNION ALL
SELECT 'desertification_risk', count(*) FROM desertification_risk;
SQL
```

---

## 部署 Checklist

在访问前过一遍：

- [ ] Docker 和 Compose 版本 `docker compose version` ≥ v2.20
- [ ] 云厂商安全组放通了 22/80/443/3000/8000
- [ ] `.env` 所有必填字段都填了（POSTGRES_PASSWORD / LLM_API_KEY / NEXT_PUBLIC_API_URL / CORS_ORIGINS）
- [ ] `secrets/gee-key.json` 已上传且 `chmod 600`
- [ ] `docker compose ps` 四个服务都 `Up` 且 healthy
- [ ] `curl http://localhost:8000/health` 返回 `{"status":"ok"}`
- [ ] `curl -I http://localhost:3000` 返回 `200`
- [ ] 浏览器访问 `http://<IP>:3000`，能看到仪表盘、点沙地、出时序图
- [ ] 试一次 RAG 问答，流式响应正常
- [ ] 如果配了 Nginx：证书正常、SSE 不断流、gzip 生效
- [ ] 备份 cron 已加

---

*维护：SandbeltOS 团队 · 最后更新：2026-04-19*

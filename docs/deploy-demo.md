# SandbeltOS · 云服务器开发阶段演示部署手册(原生安装版)

> **适用场景**:把**当前开发阶段**的 SandbeltOS 部署到一台云服务器,用于**演示**已有功能(仪表盘 + 地图 + 时序图 + RAG 问答),**不再**在服务器上跑数据采集/计算流水线(GEE / CDS / Prefect 全部不装)。
>
> **部署方式**:**全部原生安装**(不用 Docker),方便随时改代码/看日志/排查问题。
>
> **目标环境**:Ubuntu 22.04 / 24.04 LTS · 4 vCPU / 16 GB RAM / 100 GB SSD · 公网 IP `175.27.213.32`
>
> **最后更新**:2026-04-19(已兼容 Ubuntu 24.04 Noble)

---

## 目录

1. [架构速览](#1-架构速览)
2. [本机准备清单](#2-本机准备清单)
3. [Step 0 · 服务器前置](#step-0--服务器前置)
4. [Step 1 · 数据层(PostgreSQL + Redis)](#step-1--数据层postgresql--redis)
5. [Step 2 · 从本机拷数据](#step-2--从本机拷数据)
6. [Step 3 · Backend(Python)](#step-3--backendpython)
7. [Step 4 · Frontend(Node / Next.js)](#step-4--frontendnode--nextjs)
8. [Step 5 · systemd 常驻 + 验证](#step-5--systemd-常驻--验证)
9. [日常运维](#日常运维)
10. [常见问题速查](#常见问题速查)
11. [部署 Checklist](#部署-checklist)

---

## 1. 架构速览

```
浏览器  ──▶  :3000 (next start)   ──┐
                                    │ fetch /api/v1/*
浏览器  ──▶  :8000 (uvicorn)    ◀───┘
                │
                ├──▶ 127.0.0.1:5432  PostgreSQL 16 (PostGIS + TimescaleDB)
                ├──▶ 127.0.0.1:6379  Redis 7
                └──▶ ./backend/rag/chroma_store (本机文件)
```

**不跑**:GEE 采集、CDS/ERA5 下载、Prefect 定时任务、`rag.ingest`(PDF 切片)、风险计算脚本。所有数据**从本机一次性迁移过来**,服务器只读展示。

---

## 2. 本机准备清单

部署前在**你自己的 Mac**上核对下面这些文件/目录存在:

| 本机路径 | 用途 | 典型大小 |
|---|---|---|
| `/Users/liuyue/Desktop/Github_repos/SandbeltOS/` | 项目根目录 | - |
| 本机 PostgreSQL 里的 `sandbelt_db` | 要 `pg_dump` 到服务器的源库 | 几十 MB |
| `backend/rag/chroma_store/` | 向量库(bge-m3 已经生成好的) | 几百 MB |
| `~/.cache/huggingface/hub/models--BAAI--bge-m3/` | bge-m3 权重 | ~2.3 GB |
| `~/.cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3/` | bge-reranker 权重 | ~1.1 GB |

**需要的密钥/Key**:

- `LLM_API_KEY`(CSTCloud uni-api 或任何 OpenAI 兼容服务)
- **不需要** GEE / CDS key(因为不跑采集)

---

## Step 0 · 服务器前置

```bash
ssh ubuntu@175.27.213.32

# 系统更新 + 基础工具
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl gnupg lsb-release ca-certificates \
                    git vim htop tmux ufw build-essential

# 防火墙:开 SSH + 前端 + 后端
sudo ufw allow 22/tcp
sudo ufw allow 3000/tcp   # 前端
sudo ufw allow 8000/tcp   # 后端
sudo ufw --force enable
sudo ufw status

# 建项目目录
sudo mkdir -p /opt/sandbelt
sudo chown $USER:$USER /opt/sandbelt
cd /opt/sandbelt

# 拉代码
git clone https://github.com/Jiawang1209/SandbeltOS.git
cd SandbeltOS

# 建挂载/数据目录
mkdir -p secrets data/chroma data/hf_cache
```

> ⚠️ **云厂商安全组**(腾讯云控制台 → 安全组规则)**也要放通 22 / 3000 / 8000**,否则公网打不开。`ufw` 只是服务器内的一层。

---

## Step 1 · 数据层(PostgreSQL + Redis)

### 1.1 加 PGDG + TimescaleDB 两个 apt 源

> ⚠️ **Ubuntu 24.04 (Noble) 注意**:TimescaleDB 官方仓库**目前最新只发到 `jammy` (22.04)**,noble 还没发包。解决办法是把 TSDB 的 codename **写死成 `jammy`** —— TSDB 是 PG 扩展、跨 Ubuntu 版本兼容,装了能用。PGDG 仓库本身是支持 noble 的,保持 `$(lsb_release -cs)` 即可。

```bash
# —— PostgreSQL 官方源(PGDG) ——
sudo install -d /usr/share/postgresql-common/pgdg
sudo curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
  https://www.postgresql.org/media/keys/ACCC4CF8.asc
echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
  https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" | \
  sudo tee /etc/apt/sources.list.d/pgdg.list

# —— TimescaleDB 官方源 ——
# 用 gpg --dearmor 导入二进制密钥(比 .asc 文本更稳);curl 必须带 -L 跟 301 跳转
curl -fsSL https://packagecloud.io/timescale/timescaledb/gpgkey | \
  sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/timescaledb.gpg

# codename 写死 jammy(不要用 lsb_release,noble 没发包)
echo "deb [signed-by=/etc/apt/trusted.gpg.d/timescaledb.gpg] \
  https://packagecloud.io/timescale/timescaledb/ubuntu/ jammy main" | \
  sudo tee /etc/apt/sources.list.d/timescaledb.list

sudo apt update
```

**如果之前跑过旧文档版本残留了错误的 key / list 文件**,先清理再重来:

```bash
sudo rm -f /etc/apt/sources.list.d/timescaledb.list
sudo rm -f /etc/apt/trusted.gpg.d/timescaledb.asc /etc/apt/trusted.gpg.d/timescaledb.gpg
# 然后重跑上面两段
```

**apt update 输出应该干净无 GPG 错误**。`Hit / Get` 可以,不能有 `Err:` 或 `NO_PUBKEY`。

### 1.2 装包(严格版本)

```bash
sudo apt install -y \
  postgresql-16 postgresql-client-16 \
  postgresql-16-postgis-3 postgresql-16-postgis-3-scripts \
  timescaledb-2-postgresql-16 \
  redis-server

# TimescaleDB 自动改 postgresql.conf(加 shared_preload_libraries = 'timescaledb')
sudo timescaledb-tune --quiet --yes

sudo systemctl restart postgresql
sudo systemctl enable postgresql redis-server
```

**验证版本**:

```bash
sudo -u postgres psql -c "SELECT version();"
# → PostgreSQL 16.x

redis-server --version
# → Redis server v=7.x
```

### 1.3 建库 + 建用户 + 装扩展

```bash
sudo -u postgres psql <<'SQL'
CREATE USER sandbelt WITH PASSWORD '你的强密码';   -- ⚠️ 换成 openssl rand -base64 24 生成
CREATE DATABASE sandbelt_db OWNER sandbelt;
\c sandbelt_db
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;
GRANT ALL PRIVILEGES ON DATABASE sandbelt_db TO sandbelt;
GRANT ALL ON SCHEMA public TO sandbelt;
SQL
```

### 1.4 数据层验证(4 条全通才能往下走)

```bash
# ① 扩展
sudo -u postgres psql -d sandbelt_db -c \
  "SELECT extname, extversion FROM pg_extension WHERE extname IN ('postgis','timescaledb');"
# 应该有两行

# ② sandbelt 用户能连
PGPASSWORD='你的强密码' psql -h 127.0.0.1 -U sandbelt -d sandbelt_db -c "SELECT 1;"

# ③ Redis
redis-cli ping   # → PONG

# ④ 端口监听
ss -ltnp | grep -E ':(5432|6379)'
```

---

## Step 2 · 从本机拷数据

### 2.1 DB dump(本机执行)

```bash
# 本机:导出为 pg_dump 自定义压缩格式(最小最快)
cd /Users/liuyue/Desktop/Github_repos/SandbeltOS
pg_dump -U sandbelt -d sandbelt_db -Fc -f /tmp/sandbelt.dump

# 上传到服务器
scp /tmp/sandbelt.dump ubuntu@175.27.213.32:/tmp/
```

### 2.2 ChromaDB 向量库(本机执行)

```bash
cd /Users/liuyue/Desktop/Github_repos/SandbeltOS
tar czf /tmp/chroma_store.tgz -C backend/rag chroma_store
scp /tmp/chroma_store.tgz ubuntu@175.27.213.32:/tmp/
```

### 2.3 HuggingFace 模型缓存(本机执行)

> 不拷的话,服务器首次加载 RAG 会从 hf.co 下 ~3.4 GB,国内服务器可能要半小时。**强烈建议拷**。

```bash
# 本机:打包两个模型(bge-m3 + bge-reranker-v2-m3)
tar czf /tmp/hf_cache.tgz -C ~/.cache/huggingface/hub \
    models--BAAI--bge-m3 \
    models--BAAI--bge-reranker-v2-m3

scp /tmp/hf_cache.tgz ubuntu@175.27.213.32:/tmp/
```

### 2.4 在服务器上还原

```bash
ssh ubuntu@175.27.213.32
cd /opt/sandbelt/SandbeltOS

# ① 恢复 DB
PGPASSWORD='你的强密码' pg_restore \
    -h 127.0.0.1 -U sandbelt -d sandbelt_db \
    --clean --if-exists --no-owner --no-privileges \
    /tmp/sandbelt.dump

# 验证:应能看到区域数 / 生态指标数
PGPASSWORD='你的强密码' psql -h 127.0.0.1 -U sandbelt -d sandbelt_db -c "
  SELECT 'regions' AS t, count(*) FROM regions UNION ALL
  SELECT 'eco_indicators', count(*) FROM eco_indicators;
"

# ② 恢复 Chroma 向量库
mkdir -p backend/rag
tar xzf /tmp/chroma_store.tgz -C backend/rag/
ls backend/rag/chroma_store/   # 应有 chroma.sqlite3

# ③ 恢复 HF 模型缓存
mkdir -p ~/.cache/huggingface/hub
tar xzf /tmp/hf_cache.tgz -C ~/.cache/huggingface/hub/
ls ~/.cache/huggingface/hub/   # 应有两个 models--BAAI--* 目录
```

---

## Step 3 · Backend(Python)

### 3.1 装 Python 3.11

Ubuntu 22.04 自带 3.10,需要加 deadsnakes PPA 拿 3.11:

```bash
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# 装 PostGIS/GeoAlchemy 需要的系统库
sudo apt install -y libpq-dev libproj-dev libgeos-dev

python3.11 --version   # → Python 3.11.x
```

### 3.2 建 venv + 写精简 requirements.txt

```bash
cd /opt/sandbelt/SandbeltOS/backend
python3.11 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip setuptools wheel
```

**写一份只含运行时依赖的精简 requirements**(原 `requirements.txt` 里采集/计算/测试相关的一律砍掉):

```bash
cat > requirements-runtime.txt <<'EOF'
# === Web ===
fastapi>=0.110
uvicorn[standard]>=0.27

# === Database ===
sqlalchemy>=2.0
asyncpg>=0.29
psycopg2-binary>=2.9
geoalchemy2>=0.15
redis>=5.0

# === Validation & Config ===
pydantic>=2.0
pydantic-settings>=2.0

# === Geospatial (API 响应里会用到) ===
shapely>=2.0
pyproj>=3.6

# === 数据处理 ===
numpy>=1.26
pandas>=2.1

# === RAG 运行时 ===
chromadb>=0.5
FlagEmbedding>=1.2.10
langchain-community>=0.2
openai>=1.40
httpx>=0.27
EOF
```

### 3.3 先装 CPU 版 PyTorch(**关键**,省 1.5GB + 编译时间)

```bash
# FlagEmbedding 会拉 torch,默认是 CUDA 版(~2GB)。服务器无 GPU,装 CPU 版 ~200MB。
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 再装其他
pip install -r requirements-runtime.txt
```

> 如果网络慢,`pip` 加上 `-i https://pypi.tuna.tsinghua.edu.cn/simple` 走清华源。但 `torch` 那行**不能换源**(清华没有 CPU-only 索引)。

### 3.4 配 `.env`

```bash
cd /opt/sandbelt/SandbeltOS
cp .env.example .env
vim .env
```

**关键字段**(只填这些就够,其他留默认):

```ini
# === App ===
APP_ENV=production
CORS_ORIGINS=http://175.27.213.32:3000

# === Database(原生装在本机,用 127.0.0.1) ===
DATABASE_URL=postgresql+asyncpg://sandbelt:你的强密码@127.0.0.1:5432/sandbelt_db
DATABASE_URL_SYNC=postgresql://sandbelt:你的强密码@127.0.0.1:5432/sandbelt_db

# === Redis ===
REDIS_URL=redis://127.0.0.1:6379/0

# === LLM ===
LLM_BASE_URL=https://uni-api.cstcloud.cn/v1
LLM_API_KEY=你的 uni-api key
LLM_MODEL=qwen3:235b
LLM_MAX_TOKENS=2048

# === RAG ===
RAG_EMBEDDER=BAAI/bge-m3
RAG_RERANKER=BAAI/bge-reranker-v2-m3
RAG_TOP_K_RETRIEVE=20
RAG_TOP_K_RERANK=5
CHROMA_PERSIST_DIR=backend/rag/chroma_store
RAG_DOCS_DIR=backend/rag/docs

# === HF 镜像(国内服务器加速,已拷了缓存其实不走网,但万一缓存miss兜底) ===
HF_ENDPOINT=https://hf-mirror.com
```

> **不用**填 `GEE_*` / `CDS_*`,对应采集模块 API 不会启动加载。

### 3.5 手动启一次验证

```bash
cd /opt/sandbelt/SandbeltOS/backend
source .venv/bin/activate
# 注意:从 backend/ 目录启,让 uvicorn 能找到 app 和 rag 模块
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**新开一个 SSH 会话**,测一下:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok","version":"0.1.0"}

curl http://127.0.0.1:8000/api/v1/gis/regions | head -c 200
# 应返回 GeoJSON / JSON
```

验证 OK → Ctrl+C 停掉,Step 5 再用 systemd 常驻。

---

## Step 4 · Frontend(Node / Next.js)

> ⚠️ **注意**:本项目 Next.js 版本是 **16.2.4**,和网上大部分(13/14/15)的写法**有破坏性差异**。遇到任何 API 疑问,**直接读服务器上 `frontend/node_modules/next/dist/docs/` 里的文档**,不要凭记忆写。

### 4.1 装 Node 20

```bash
# 官方 NodeSource 仓库
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

node --version   # → v20.x
npm --version    # → 10.x
```

### 4.2 构建前端

```bash
cd /opt/sandbelt/SandbeltOS/frontend

# 注入 build-time 变量(Next.js 的 NEXT_PUBLIC_* 在 build 时被 inline 进 bundle)
export NEXT_PUBLIC_API_URL=http://175.27.213.32:8000

npm ci                    # 严格用 package-lock.json,~1-2 min
npm run build             # Next.js production build,~2-4 min
```

> 如果 `npm ci` 卡,换淘宝源:`npm ci --registry=https://registry.npmmirror.com`

### 4.3 手动起一次验证

```bash
cd /opt/sandbelt/SandbeltOS/frontend
# 同样要把 NEXT_PUBLIC_API_URL 放进环境,虽然已经 inline,某些 runtime 路径还会读
NEXT_PUBLIC_API_URL=http://175.27.213.32:8000 \
  npx next start -p 3000 -H 0.0.0.0
```

浏览器开 `http://175.27.213.32:3000`,看到仪表盘 + 数据能加载 = OK。Ctrl+C 停掉。

---

## Step 5 · systemd 常驻 + 验证

### 5.1 Backend 服务单元

```bash
sudo tee /etc/systemd/system/sandbelt-backend.service >/dev/null <<'EOF'
[Unit]
Description=SandbeltOS FastAPI Backend
After=network.target postgresql.service redis-server.service
Requires=postgresql.service redis-server.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/sandbelt/SandbeltOS/backend
EnvironmentFile=/opt/sandbelt/SandbeltOS/.env
ExecStart=/opt/sandbelt/SandbeltOS/backend/.venv/bin/uvicorn app.main:app \
          --host 0.0.0.0 --port 8000 --workers 1
Restart=on-failure
RestartSec=5
# RAG 首次加载模型会用到比较多内存,别限太死
MemoryHigh=8G

[Install]
WantedBy=multi-user.target
EOF
```

### 5.2 Frontend 服务单元

```bash
sudo tee /etc/systemd/system/sandbelt-frontend.service >/dev/null <<'EOF'
[Unit]
Description=SandbeltOS Next.js Frontend
After=network.target sandbelt-backend.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/sandbelt/SandbeltOS/frontend
Environment=NODE_ENV=production
Environment=NEXT_PUBLIC_API_URL=http://175.27.213.32:8000
Environment=PORT=3000
Environment=HOSTNAME=0.0.0.0
ExecStart=/usr/bin/npx next start -p 3000 -H 0.0.0.0
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

### 5.3 启用并启动

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sandbelt-backend sandbelt-frontend

# 看状态
systemctl status sandbelt-backend --no-pager
systemctl status sandbelt-frontend --no-pager

# 实时日志
sudo journalctl -u sandbelt-backend -f
sudo journalctl -u sandbelt-frontend -f
```

### 5.4 最终验证

```bash
# 从服务器自身
curl http://127.0.0.1:8000/health
curl -I http://127.0.0.1:3000

# 从本机
curl http://175.27.213.32:8000/health
open http://175.27.213.32:3000      # 浏览器打开
```

**看到仪表盘 + 地图能加载 + 时序图能画 + RAG 聊天能流式回答 = 部署成功**。

---

## 日常运维

### 改代码后重新部署

```bash
cd /opt/sandbelt/SandbeltOS
git pull

# 只改了 backend Python 代码
sudo systemctl restart sandbelt-backend

# 改了 backend 依赖(requirements-runtime.txt 变了)
source backend/.venv/bin/activate
pip install -r backend/requirements-runtime.txt
sudo systemctl restart sandbelt-backend

# 改了 frontend 代码
cd frontend
NEXT_PUBLIC_API_URL=http://175.27.213.32:8000 npm run build
sudo systemctl restart sandbelt-frontend

# 改了 frontend 依赖(package.json 变了)
npm ci && NEXT_PUBLIC_API_URL=http://175.27.213.32:8000 npm run build
sudo systemctl restart sandbelt-frontend
```

### 更新 DB 数据

```bash
# 本机
pg_dump -U sandbelt -d sandbelt_db -Fc -f /tmp/sandbelt.dump
scp /tmp/sandbelt.dump ubuntu@175.27.213.32:/tmp/

# 服务器
sudo systemctl stop sandbelt-backend
PGPASSWORD='xxx' pg_restore -h 127.0.0.1 -U sandbelt -d sandbelt_db \
    --clean --if-exists --no-owner --no-privileges /tmp/sandbelt.dump
sudo systemctl start sandbelt-backend
```

### 看日志

```bash
sudo journalctl -u sandbelt-backend -f                # 实时
sudo journalctl -u sandbelt-backend --since "10 min ago"
sudo journalctl -u sandbelt-backend --no-pager -n 200  # 最后 200 行
```

### 停 / 重启

```bash
sudo systemctl restart sandbelt-backend
sudo systemctl restart sandbelt-frontend
sudo systemctl stop sandbelt-backend sandbelt-frontend
```

---

## 常见问题速查

| 症状 | 可能原因 & 排查 |
|---|---|
| `pip install FlagEmbedding` 卡在 torch | 没先装 CPU 版 torch。按 §3.3 先跑 `pip install torch --index-url ...cpu` |
| backend 启动报 `ImportError: cannot import name 'ee'` | 精简版少装了 `earthengine-api`,但某处模块级 import 了 `ee`。临时 `pip install earthengine-api`,或把对应 route 从 `app/main.py` 的 `include_router` 注释掉 |
| backend 启动报 `fitz not found` | 同上,但这次是 `PyMuPDF`:`pip install PyMuPDF langchain-text-splitters` |
| backend 启动很慢(1-2 分钟) | 正常。RAG 首次加载 bge-m3 + reranker 到内存(~3GB),之后请求秒回 |
| 前端白屏,F12 看到 `Refused to connect to http://localhost:8000` | `NEXT_PUBLIC_API_URL` 没在 build 时注入。重 build:`export NEXT_PUBLIC_API_URL=http://175.27.213.32:8000 && npm run build` |
| 前端能开,但所有 API 请求 CORS 报错 | `.env` 里 `CORS_ORIGINS` 和浏览器地址不完全一致(协议/端口/斜杠) |
| `curl 127.0.0.1:8000/health` 通但外网打不开 | 云厂商安全组没放通 8000 |
| PG 启动失败,`shared_preload_libraries` 找不到 timescaledb | `sudo timescaledb-tune --quiet --yes` 再 `sudo systemctl restart postgresql` |
| Redis 连不上 | 默认只监听 127.0.0.1,本机服务访问没问题。如需外部访问改 `/etc/redis/redis.conf` 的 `bind`(**不建议**公网暴露) |
| journalctl 看到 `OSError: [Errno 28] No space left on device` | 磁盘满。`df -h` 看,`data/hf_cache/` + venv 容易吃空间 |

---

## 部署 Checklist

访问前过一遍:

- [ ] 云厂商安全组 + `ufw` 都放通了 22 / 3000 / 8000
- [ ] `psql` 能用 sandbelt 用户登进 sandbelt_db
- [ ] `SELECT count(*) FROM regions;` > 0(数据迁移成功)
- [ ] `ls backend/rag/chroma_store/chroma.sqlite3` 存在
- [ ] `ls ~/.cache/huggingface/hub/models--BAAI--bge-m3/` 有内容
- [ ] `.env` 里 `DATABASE_URL` 用 `127.0.0.1`、`CORS_ORIGINS` = `http://175.27.213.32:3000`、`NEXT_PUBLIC_API_URL` = `http://175.27.213.32:8000`
- [ ] `systemctl status sandbelt-backend` = active (running)
- [ ] `systemctl status sandbelt-frontend` = active (running)
- [ ] 本机浏览器 `http://175.27.213.32:3000` 能开,仪表盘数据正常加载
- [ ] 试一次 RAG 问答,流式回答正常

---

*维护:SandbeltOS · 原生部署演示版*

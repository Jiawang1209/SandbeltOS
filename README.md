# SandbeltOS · 三北防护林智慧生态决策支持系统

> **Smart Ecological Decision Support System for the Three-North Shelterbelt Program**
>
> 面向三北防护林工程区的全栈生态智能平台：实时遥感数据采集、生态指标计算、沙化风险评估、RAG 智慧问答、GIS 可视化。

---

## ✨ 核心能力

- **遥感数据入库** — MODIS NDVI / LST / SMAP / ERA5 气象，按区域按时序入 PostGIS
- **生态评估引擎** — FVC、风蚀模数、防风固沙服务量、碳密度、综合沙化风险等级
- **地图与仪表盘** — MapLibre 双沙地视图 + ECharts 时序分析 + 像素级热点
- **RAG 智慧问答** — 文献语料 + 实时指标融合的决策问答（SSE 流式）
- **预测与情景分析** — Prophet/LSTM 未来 NDVI 预测 + 造林情景模拟

---

## 🧱 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI · SQLAlchemy · PostgreSQL + PostGIS (+ TimescaleDB 可选) · Redis |
| 前端 | Next.js 16 · React 19 · MapLibre GL · ECharts · Tailwind CSS 4 |
| 数据采集 | Google Earth Engine · Copernicus CDS · Prefect |
| RAG | ChromaDB · BAAI/bge-m3 · BAAI/bge-reranker-v2-m3 · OpenAI-compatible LLM |
| ML | Prophet · scikit-learn · (可选) PyTorch LSTM |
| 运行环境 | Python 3.11 · Node.js 20 |

---

## 📁 项目结构

```
SandbeltOS/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── main.py            # 应用入口
│   │   ├── config.py          # 环境配置
│   │   ├── api/v1/            # 路由：ecological / gis / grid / basemap / chat
│   │   ├── models/            # SQLAlchemy 模型
│   │   └── services/          # 业务服务
│   ├── rag/                   # RAG 管线（切片、向量化、检索、重排、LLM）
│   ├── scripts/               # 数据采集与初始化脚本
│   ├── sql/init.sql           # 数据库初始化 SQL
│   └── requirements.txt
├── frontend/                   # Next.js 前端
│   ├── src/app/               # App Router 页面
│   ├── src/components/        # 地图、图表、对话组件
│   └── package.json
├── data/                       # 边界、采样、RAG 原始文档（不进 Git）
├── docs/
│   ├── ARCHITECTURE.md        # 架构图、Schema、代码模板
│   └── DEPLOYMENT.md          # 部署指南
├── PLAN.md                     # 分阶段开发计划（Phase 0 → Phase 5）
└── .env.example                # 环境变量模板
```

---

## 🚀 快速开始（本地开发）

### 1. 前置准备

| 事项 | 说明 |
|---|---|
| GEE 账号 | 注册 Google Earth Engine，开通用于遥感项目的服务账号 |
| CDS API | 注册 [climate.copernicus.eu](https://climate.copernicus.eu) 并拿到 API key |
| LLM API | OpenAI-兼容接口皆可（默认：中科院 uni-api `qwen3:235b`） |
| Miniforge | 推荐用 conda 创建环境 `sandbelt`（见 PLAN.md） |

### 2. 环境搭建

```bash
# 创建 Python + Node 环境
conda create -n sandbelt python=3.11 -y
conda activate sandbelt
conda install -c conda-forge \
    postgresql=16 postgis redis-server \
    gdal rasterio geopandas shapely fiona pyproj \
    nodejs=20 -y

# Python 依赖
cd backend && pip install -r requirements.txt && cd ..

# 前端依赖
cd frontend && npm ci && cd ..
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 填入 DATABASE_URL / LLM_API_KEY / GEE_KEY_FILE 等
```

### 4. 初始化数据库

```bash
conda activate sandbelt
initdb -D $CONDA_PREFIX/var/postgresql -U sandbelt --pwprompt
pg_ctl -D $CONDA_PREFIX/var/postgresql -l $CONDA_PREFIX/var/postgresql/logfile start
createdb -U sandbelt sandbelt_db
psql -U sandbelt -d sandbelt_db -f backend/sql/init.sql
```

### 5. 启动

```bash
# 终端 1：后端
conda activate sandbelt
cd backend && uvicorn app.main:app --reload --port 8000

# 终端 2：前端
cd frontend && npm run dev
```

打开 <http://localhost:3000> 查看仪表盘，<http://localhost:8000/docs> 查看 API。

---

## 💻 本地开发 Web 调用方法

### 前端页面入口（Next.js · 默认端口 3000）

| 页面 | URL | 说明 |
|---|---|---|
| 首页 | <http://localhost:3000> | 项目介绍 / 入口导航 |
| 仪表盘 | <http://localhost:3000/dashboard> | 双沙地地图 + 生态指标 + 像素热点 |
| RAG 问答 | <http://localhost:3000/chat> | 文献 + 实时指标融合的流式对话 |

> 前端通过 `NEXT_PUBLIC_API_URL` 环境变量访问后端。本地默认 `http://localhost:8000`，跨设备访问改成局域网 IP 后需重启 `npm run dev`。

### 后端 API 入口（FastAPI · 默认端口 8000）

| 地址 | 用途 |
|---|---|
| <http://localhost:8000/docs> | Swagger UI（可直接点按钮试调） |
| <http://localhost:8000/redoc> | ReDoc 文档视图 |
| <http://localhost:8000/openapi.json> | OpenAPI 规范 JSON |
| <http://localhost:8000/health> | 健康检查 |

### 常用接口 curl 示例

```bash
# 健康检查
curl http://localhost:8000/health

# 区域 GeoJSON（地图边界）
curl "http://localhost:8000/api/v1/gis/regions"

# 生态指标时序（科尔沁沙地 NDVI，2020-2024）
curl "http://localhost:8000/api/v1/ecological/timeseries?region=horqin&metric=ndvi&start=2020-01-01&end=2024-12-31"

# 当前综合状态
curl "http://localhost:8000/api/v1/ecological/current-status?region=otindag"

# 像素级 NDVI 栅格
curl "http://localhost:8000/api/v1/grid/ndvi?region=horqin&date=2024-08-01"

# RAG 问答（SSE 流式，加 -N 看实时分片）
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"科尔沁沙地近五年植被恢复情况如何？","region":"horqin"}'
```

### 跨端/局域网访问

```bash
# 后端监听所有网卡
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端开启 LAN
cd frontend && npm run dev -- -H 0.0.0.0
```

用 `ipconfig getifaddr en0`（macOS）拿到局域网 IP，在手机/平板浏览器访问 `http://<你的IP>:3000`；记得把 `.env` 的 `NEXT_PUBLIC_API_URL` 和 `CORS_ORIGINS` 改成对应地址后**重启前端 dev server**（`NEXT_PUBLIC_*` 在启动时 inline）。

### 前端直接调用后端（浏览器控制台快速试）

```js
// 在 http://localhost:3000 的 DevTools Console
fetch('http://localhost:8000/api/v1/ecological/current-status?region=horqin')
  .then(r => r.json()).then(console.log)
```

### 常见排错

| 现象 | 原因 & 解决 |
|---|---|
| 前端报 CORS 错 | `.env` 的 `CORS_ORIGINS` 没包含当前前端地址，改完重启后端 |
| 地图/图表空白 | 后端未启动或 `NEXT_PUBLIC_API_URL` 指错，打开 Network 面板确认 4xx/5xx |
| SSE 流一次性返回 | 反代关闭了 buffering；本地直连不会有此问题，部署时见 `docs/DEPLOYMENT.md` 的 Nginx 配置 |
| `/api/v1/*` 返回 404 | 后端未加载对应路由模块，检查 `backend/app/api/v1/__init__.py` |

---

## 📡 API 速查

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/health` | 健康检查 |
| GET | `/api/v1/gis/regions` | 区域 GeoJSON |
| GET | `/api/v1/ecological/timeseries` | 生态指标时序 |
| GET | `/api/v1/ecological/current-status` | 区域综合状态 |
| GET | `/api/v1/grid/*` | 像素级 NDVI / 热点 |
| GET | `/api/v1/basemap/*` | 卫星底图代理 |
| POST | `/api/v1/chat/stream` | RAG 问答（SSE 流式） |

---

## 🚢 部署到云服务器

完整部署手册见 **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**，涵盖：

- 服务器规格选型与前置环境
- 打包清单（什么要带、什么一定不要带）
- Docker Compose 一键全栈（推荐）
- systemd 原生部署备选方案
- Vercel 前端 + 服务器后端的混合方案
- PostgreSQL / ChromaDB 数据迁移
- Nginx + HTTPS + SSE 流式配置
- 备份、日志轮转、常见问题排错

> **TL;DR**：服务器装好 Docker，填好 `.env`，`docker compose up -d --build` 起全栈；Nginx 反代 + Certbot 签 HTTPS；`pg_dump` 把本地数据带过去。

---

## 🧭 开发路线图

详见 **[PLAN.md](PLAN.md)** —— 6 个阶段分解：

- ✅ Phase 0 · 项目骨架
- ✅ Phase 1 · 数据入库
- ✅ Phase 2 · 基础可视化
- 🟡 Phase 3 · 生态评估引擎
- 🟡 Phase 4 · RAG 问答
- ⏳ Phase 5 · 预测 + 情景分析

---

## 📖 文档索引

| 文档 | 内容 |
|---|---|
| [PLAN.md](PLAN.md) | 分阶段开发计划、任务清单、验收标准 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构图、数据库 Schema、代码模板 |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | 云服务器部署指南 |
| [.env.example](.env.example) | 环境变量模板 |

---

## 📜 License

本项目暂未开源。

---

*维护：SandbeltOS 团队*

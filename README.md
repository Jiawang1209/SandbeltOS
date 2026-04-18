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

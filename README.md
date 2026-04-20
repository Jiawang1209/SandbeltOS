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

### 前端（Frontend）

| 组件 | 选型 | 版本 | 作用 |
|---|---|---|---|
| 框架 | **Next.js** (App Router) | 16.x | 服务端渲染 + React 路由 |
| UI 库 | **React** | 19.x | 组件框架 |
| 语言 | **TypeScript** | 5.x | 类型安全 |
| 样式 | **Tailwind CSS** | 4.x | 原子化 CSS |
| 地图 | **MapLibre GL JS** | 4.x | 矢量地图渲染（双沙地视图） |
| 图表 | **Apache ECharts** | 5.x | 时序分析 / 栅格热力图 |
| 运行时 | **Node.js** | 20.x | 构建和 SSR |
| 端口 | — | **3000** | 浏览器访问 |

### 后端（Backend）

| 组件 | 选型 | 版本 | 作用 |
|---|---|---|---|
| 框架 | **FastAPI** | 0.115+ | 异步 REST API + SSE 流式 |
| ASGI 服务器 | **Uvicorn** | 0.32+ | 运行时 |
| ORM | **SQLAlchemy** (async) | 2.0+ | 数据库访问层 |
| 驱动 | **asyncpg** + **psycopg2** | — | 异步/同步 PostgreSQL 驱动 |
| 空间数据 | **GeoAlchemy2** · **geopandas** · **rasterio** · **shapely** · **fiona** · **pyproj** | — | PostGIS ORM + 栅格 / 矢量处理 |
| 语言 | **Python** | 3.11 | |
| 端口 | — | **8000** | API · `/docs` Swagger · `/redoc` |

### 数据库（Database）

| 组件 | 选型 | 版本 | 作用 |
|---|---|---|---|
| 主库 | **PostgreSQL** | 16 | 关系型存储 |
| 空间扩展 | **PostGIS** | 3.4+ | 地理空间查询（`regions`, `pixels`） |
| 时序扩展 | **TimescaleDB** | 2.x（可选） | 生态指标时序超表 |
| 镜像 | `timescale/timescaledb-ha:pg16` | — | 同时自带 PostGIS 和 TimescaleDB |
| 端口 | — | **5432**（仅容器内网） | |

### 缓存（Cache）

| 组件 | 选型 | 版本 | 作用 |
|---|---|---|---|
| 缓存 / 队列 | **Redis** | 7-alpine | 会话 · GEE 请求缓存 · 限流 |
| 持久化 | **AOF** 模式 | — | `data/redis/` 宿主机挂载 |
| 端口 | — | **6379**（仅容器内网） | |

### RAG 向量库 & LLM 管线

| 组件 | 选型 | 版本/模型 | 作用 |
|---|---|---|---|
| 向量库 | **ChromaDB** | — | 语料片段持久化（`data/chroma/`） |
| 嵌入模型 | **BAAI/bge-m3** | ~2.0 GB | 文档 & 查询 embedding |
| 重排模型 | **BAAI/bge-reranker-v2-m3** | ~1.1 GB | Top-K 精排 |
| 加载器 | **FlagEmbedding** · **HuggingFace Transformers** | — | 本地加载 |
| LLM 客户端 | **OpenAI-compatible** | — | 默认：中科院 uni-api `qwen3:235b` |
| 框架 | **LangChain** | — | 链路编排 |
| 文档切分 | chunk_size=800 · overlap=100 | — | 配置见 `.env` |
| 流式 | **SSE**（Server-Sent Events） | — | `POST /api/v1/chat/stream` |

### 机器学习（ML / 预测）

| 组件 | 选型 | 作用 |
|---|---|---|
| 时序预测 | **Prophet** · **scikit-learn** · (可选) **PyTorch LSTM** | 未来 NDVI / 生态指标预测 |
| 数据处理 | **xarray** · **netCDF4** · **pandas** · **numpy** | 多维栅格数据 / 表格运算 |

### 数据采集（Data Ingestion）

| 组件 | 来源 | 用途 |
|---|---|---|
| **Google Earth Engine** | MODIS NDVI / LST · SMAP · Landsat | 遥感影像与指标 |
| **Copernicus CDS** | ERA5 气象再分析 | 风速 / 降水 / 气温 |
| **Prefect** | — | 定时 ETL 工作流编排 |

### 部署与基础设施（DevOps）

| 组件 | 选型 | 作用 |
|---|---|---|
| 容器化 | **Docker** · **Docker Compose** | 一键全栈编排 |
| 反向代理 | **Nginx** + **Certbot**（生产） | 域名 / HTTPS / SSE 兼容 |
| 服务进程 | **systemd**（备选方案） | 非容器部署 |
| CI/CD | GitHub | 源码托管 |
| 密钥托管 | `secrets/` 目录（gitignore） | GEE service account |

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

**三份文档，按需挑一个：**

| 场景 | 文档 | 耗时 |
|---|---|---|
| **最快上手**：只想几分钟内跑起来 | **[QUICKSTART_CN.md](QUICKSTART_CN.md)** + `bash deploy.sh` | 15–30 分钟 |
| **方案对比**：想知道 Docker / systemd / Vercel 各自利弊 | **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** | — |
| **手把手 Docker**：一步步跟着做，踩坑说明最全 | **[docs/docker.md](docs/docker.md)** | 参考手册 |

**TL;DR（Docker Compose 方式）：**

```bash
# 1. 登录服务器拉代码
git clone https://github.com/Jiawang1209/SandbeltOS.git /opt/sandbelt/SandbeltOS
cd /opt/sandbelt/SandbeltOS

# 2. 一键部署脚本：装 Docker、建目录、校验 .env、启动
bash deploy.sh

# 3. 首次会生成 .env，编辑好后再跑一次
vim .env    # 必改：POSTGRES_PASSWORD / LLM_API_KEY / NEXT_PUBLIC_API_URL / CORS_ORIGINS
bash deploy.sh

# 4. 访问
# 浏览器：http://<服务器IP>:3000
# Swagger：http://<服务器IP>:8000/docs
```

> 要 HTTPS + 域名？`docs/docker.md` 附录 A 有 Nginx + Certbot 的完整配置。

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
| [QUICKSTART_CN.md](QUICKSTART_CN.md) | 部署快速开始（3 步上线） |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | 部署方案对比（Docker / systemd / Vercel） |
| [docs/docker.md](docs/docker.md) | Docker 部署完全手册（含 Nginx + HTTPS） |
| [deploy.sh](deploy.sh) | 一键部署脚本（装 Docker + 校验 .env + 启动） |
| [scripts/deploy/export_local_data.sh](scripts/deploy/export_local_data.sh) | 本地数据导出（PostgreSQL + ChromaDB + PDF） |
| [scripts/deploy/import_to_server.sh](scripts/deploy/import_to_server.sh) | 服务器端数据导入 |
| [.env.example](.env.example) | 环境变量模板 |

---

## 📜 License

本项目暂未开源。

---

*维护：SandbeltOS 团队*

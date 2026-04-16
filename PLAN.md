# SandbeltOS — 可执行开发计划

> **三北防护林智慧生态决策支持系统**
> Smart Ecological Decision Support System for the Three-North Shelterbelt Program

---

## 项目定位

面向三北防护林工程区的全栈生态智能平台，集实时遥感数据采集、生态指标计算、预测预警、RAG 智慧问答、GIS 可视化于一体。

**核心约束**：完全依赖开放数据，Miniforge 本地开发（不用 Docker），个人开发者节奏。

---

## 技术栈速览

| 层 | 选型 |
|----|------|
| 后端 | FastAPI + SQLAlchemy + TimescaleDB/PostGIS |
| 前端 | Next.js 14 + Deck.gl + ECharts + Shadcn/ui |
| 数据采集 | earthengine-api + cdsapi + Prefect |
| RAG | LangChain + ChromaDB + Claude API |
| ML | Prophet（基线）+ PyTorch LSTM（进阶） |
| 环境 | Miniforge conda env `sandbelt` (Python 3.11 + Node.js 20) |

> 完整架构图、数据库 Schema、代码模板详见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## 前置准备（在写任何代码之前必须完成）

| # | 事项 | 预估耗时 | 状态 |
|---|------|---------|------|
| P1 | 注册 GEE 研究账号（说明用途：三北防护林生态监测研究） | 1-3 工作日审核 | [ ] |
| P2 | 注册 ERA5 CDS API 账号（climate.copernicus.eu） | 即时 | [ ] |
| P3 | 注册 NESDC 账号，下载三北工程区矢量边界数据 | 1-2 天 | [ ] |
| P4 | 获取 Anthropic API Key | 即时 | [ ] |
| P5 | 获取 OpenAI API Key（用于 embedding）或确认用本地 bge-m3 | 即时 | [ ] |
| P6 | 搭建 conda `sandbelt` 环境（见下方脚本） | 30 min | [ ] |
| P7 | 初始化 PostgreSQL + TimescaleDB + PostGIS 本地实例 | 30 min | [ ] |
| P8 | 收集 RAG 初始语料：至少 5 篇核心文献 PDF | 2-3 天 | [ ] |

### 环境搭建脚本

```bash
# 创建环境
conda create -n sandbelt python=3.11 -y
conda activate sandbelt

# 数据库 + 缓存 + 地理空间 + ML + 前端
conda install -c conda-forge \
    postgresql=16 timescaledb postgis redis-server \
    gdal rasterio geopandas shapely fiona pyproj netcdf4 hdf5 \
    pytorch cpuonly nodejs=20 -y

# Python 依赖
pip install fastapi "uvicorn[standard]" sqlalchemy psycopg2-binary asyncpg \
    geoalchemy2 redis pydantic pydantic-settings \
    earthengine-api cdsapi xarray numpy pandas scipy \
    scikit-learn prophet \
    langchain langchain-anthropic langchain-openai langchain-community \
    chromadb pypdf anthropic openai prefect

# 前端依赖（Phase 3 再执行）
# cd frontend && npm install
```

### PostgreSQL 初始化

```bash
conda activate sandbelt
initdb -D $CONDA_PREFIX/var/postgresql -U sandbelt --pwprompt
echo "shared_preload_libraries = 'timescaledb'" >> $CONDA_PREFIX/var/postgresql/postgresql.conf
pg_ctl -D $CONDA_PREFIX/var/postgresql -l $CONDA_PREFIX/var/postgresql/logfile start
createdb -U sandbelt sandbelt_db
psql -U sandbelt -d sandbelt_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
psql -U sandbelt -d sandbelt_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

---

## 阶段划分

整个项目分为 **6 个阶段**，采用递进式交付。每个阶段结束都有一个**可演示的产出物**。

| 阶段 | 名称 | 核心产出 | 预估周期 |
|------|------|---------|---------|
| Phase 0 | 项目骨架 | 空项目能跑起来（前后端 hello world） | 2 天 |
| Phase 1 | 数据入库 | GEE/ERA5 数据拉取 → 写入 TimescaleDB | 1-2 周 |
| Phase 2 | 基础可视化 | 前端地图 + 时序图展示真实数据 | 1-2 周 |
| Phase 3 | 生态评估引擎 | 指标计算 + 风险评估 + 预警 | 2 周 |
| Phase 4 | RAG 问答 | 文献入库 + 流式问答界面 | 2 周 |
| Phase 5 | 预测 + 情景分析 | Prophet/LSTM 预测 + 造林情景模拟 | 2 周 |

**总计：约 10-12 周（个人开发者节奏，非全职则翻倍）**

---

## Phase 0 — 项目骨架（2 天）

> **目标**：前后端空项目跑通，数据库连通，CI 级别的基础验证。

### 任务

| # | 任务 | 前置 | 验收标准 |
|---|------|------|---------|
| 0.1 | 创建目录结构：`backend/`, `frontend/`, `data/`, `docs/` | P6 完成 | 目录存在 |
| 0.2 | 后端：FastAPI 最小入口 `main.py`，含 `/health` 端点 | 0.1 | `curl localhost:8000/health` 返回 `{"status": "ok"}` |
| 0.3 | 数据库连接：SQLAlchemy engine + `regions` 表建表 | P7 完成 | `psql` 能查到 `regions` 表 |
| 0.4 | 前端：`npx create-next-app` 初始化，能访问首页 | 0.1 | `localhost:3000` 显示页面 |
| 0.5 | 前后端联通：前端调 `/health`，展示后端状态 | 0.2, 0.4 | 页面上显示后端状态 |
| 0.6 | `.env.example` + `.gitignore` 配置 | 0.1 | 无密钥泄露风险 |
| 0.7 | 将 ARCHITECTURE.md 从 PLAN.md 拆出，移入 `docs/` | — | 代码示例和 schema 都在 docs/ |

### Phase 0 完成标志

- [x] `uvicorn app.main:app --reload` 启动无报错 ✅ 2026-04-16
- [x] `npm run dev` 启动无报错 ✅ 2026-04-16
- [x] 前端页面能显示后端 health 状态 ✅ 2026-04-16

> **备注**：PostgreSQL 16 通过 Homebrew 安装。PostGIS/TimescaleDB 扩展需 PG17+，将在 Phase 1 升级解决。

---

## Phase 1 — 数据入库（1-2 周）

> **目标**：科尔沁沙地 2020-2024 年 MODIS NDVI + ERA5 气象数据入库。
>
> **降级方案**：如果 GEE 账号未批，用 NESDC 静态 CSV 数据先跑通链路。

### 任务

| # | 任务 | 前置 | 验收标准 |
|---|------|------|---------|
| 1.1 | 建表：`eco_indicators` + `weather_data` 超表 | Phase 0 | `\d eco_indicators` 显示正确 schema |
| 1.2 | 导入三北工程区矢量边界到 `regions` 表 | P3 数据下载完成 | `SELECT count(*) FROM regions` > 0，且 `geom` 非空 |
| 1.3 | 实现 `gee_service.py`：MODIS NDVI 拉取 | P1 GEE 账号 | 函数返回 DataFrame 且行数 > 0 |
| 1.4 | 实现 `era5_service.py`：气象数据拉取 | P2 CDS 账号 | 函数返回 DataFrame 且行数 > 0 |
| 1.5 | 写入逻辑：GEE 数据 → `eco_indicators` 表 | 1.1, 1.3 | `SELECT count(*) FROM eco_indicators WHERE indicator='ndvi'` > 0 |
| 1.6 | 写入逻辑：ERA5 数据 → `weather_data` 表 | 1.1, 1.4 | `SELECT count(*) FROM weather_data` > 0 |
| 1.7 | 实现 API：`GET /api/v1/ecological/timeseries` | 1.5 | curl 返回 JSON 含 NDVI 时序数据 |
| 1.8 | 单元测试：数据拉取和写入 | 1.5, 1.6 | `pytest tests/test_gee.py` 通过 |

### 降级路径（GEE 未批时）

```
1.3* 替代：从 NESDC 下载 MODIS NDVI 离线数据集（.tif），
     用 rasterio 按区域提取均值，生成与 gee_service 相同格式的 DataFrame。
1.4* 替代：从 ERA5 网页端手动下载 .nc 文件，xarray 读取。
```

### Phase 1 完成标志

- [x] 数据库中有科尔沁沙地 2020-2024 的 NDVI 时序（约 100+ 条记录） ✅ 2026-04-16 (115 NDVI + 115 EVI)
- [x] 数据库中有同期气象数据 ✅ 2026-04-16 (1827 daily records)
- [x] API 能返回指定区域的时序数据 ✅ 2026-04-16 (GET /api/v1/ecological/timeseries)

> **备注**：Phase 1 使用合成数据完成链路验证（GEE/ERA5 账号待接入）。28 个测试全部通过。

---

## Phase 2 — 基础可视化（1-2 周）

> **目标**：在浏览器地图上看到科尔沁沙地的 NDVI 分布和时序变化。

### 任务

| # | 任务 | 前置 | 验收标准 |
|---|------|------|---------|
| 2.1 | 地图组件：Deck.gl + Maplibre 底图加载 | Phase 0 前端 | 地图能拖拽缩放 |
| 2.2 | 三北工程区边界图层：从 API 加载 GeoJSON 渲染 | 1.2, 2.1 | 地图上显示三北边界轮廓 |
| 2.3 | NDVI 热力图层：从 API 获取数据渲染 HeatmapLayer | 1.7, 2.1 | 地图上显示 NDVI 颜色分布 |
| 2.4 | 时序折线图：ECharts 展示 NDVI 时序 | 1.7 | 图表显示 4 年 NDVI 变化趋势 |
| 2.5 | 区域选择联动：点击地图区域 → 更新时序图 | 2.3, 2.4 | 点击不同区域，折线图数据跟着变 |
| 2.6 | 页面布局：左地图 + 右仪表盘的基本布局 | 2.1 | 页面不挤、不乱 |
| 2.7 | API 层：`GET /api/v1/gis/regions` 返回 GeoJSON | 1.2 | curl 返回合法 GeoJSON |

### Phase 2 完成标志

- [x] 浏览器中看到三北区域地图 + NDVI 热力图 ✅ 2026-04-16 (三北防护林边界 + 科尔沁/浑善达克沙地 NDVI 着色)
- [x] 能点击区域查看该区域 NDVI 时序折线 ✅ 2026-04-16 (点击地图或标签切换，右侧面板联动)
- [x] 截图可作为阶段性成果展示 ✅ 2026-04-16

---

## Phase 3 — 生态评估引擎（2 周）

> **目标**：核心生态指标计算 + 风险评估 + 自动预警。

### 任务

| # | 任务 | 前置 | 验收标准 |
|---|------|------|---------|
| 3.1 | 实现 `indicator_service.py`：FVC 计算 | Phase 1 数据 | `calculate_fvc(0.3)` 返回合理值 |
| 3.2 | 实现风蚀模数计算（RWEQ 简化版） | 3.1 | 给定参数返回 t/(km2·month) 量级 |
| 3.3 | 实现防风固沙服务量计算 | 3.2 | 输出 >= 0 |
| 3.4 | 实现碳密度估算 | 3.1 | 输出 gC/m2 量级 |
| 3.5 | 实现综合沙化风险评估函数 | 3.1-3.4 | 返回 risk_level 1-4 + risk_score 0-1 |
| 3.6 | 建表：`desertification_risk` + `alerts` | Phase 0 DB | 表存在 |
| 3.7 | 批量计算：对已有数据运行指标计算，结果入库 | 3.5, 3.6 | `desertification_risk` 有数据 |
| 3.8 | 预警逻辑：risk_level >= 3 时自动写入 `alerts` | 3.7 | `alerts` 表有高风险记录 |
| 3.9 | API：`GET /api/v1/ecological/current-status` | 3.7 | 返回综合状态 JSON |
| 3.10 | 前端：4 个指标卡（NDVI、FVC、风险等级、碳汇） | 3.9, Phase 2 | 仪表盘显示 4 个数字卡片 |
| 3.11 | 前端：沙化风险等级图层（红/橙/黄/绿） | 3.7, Phase 2 | 地图上能切换查看风险图层 |
| 3.12 | 前端：预警通知栏 | 3.8 | 有预警时顶部显示红色条 |
| 3.13 | Prefect 定时 flow：每 16 天拉 NDVI + 每日拉气象 | 1.3, 1.4 | Prefect UI 显示 flow 正常调度 |
| 3.14 | 单元测试：所有指标计算函数 | 3.1-3.5 | `pytest tests/test_indicators.py` 通过 |

### Phase 3 完成标志

- [ ] 仪表盘显示指标卡和预警
- [ ] 地图能切换 NDVI/风险 两个图层
- [ ] Prefect 定时任务在跑

---

## Phase 4 — RAG 问答（2 周）

> **目标**：用户能用自然语言提问，系统结合实时数据 + 文献给出回答。

### 任务

| # | 任务 | 前置 | 验收标准 |
|---|------|------|---------|
| 4.1 | 收集并整理 RAG 语料：≥10 篇文献 PDF/TXT | P8 | `rag/docs/` 下有 10+ 个文件 |
| 4.2 | 实现 `rag/ingest.py`：PDF 切片 + ChromaDB 入库 | 4.1 | 运行后 ChromaDB 集合有 500+ 文档块 |
| 4.3 | 实现 `rag/retriever.py`：向量检索封装 | 4.2 | 给定查询返回 top-5 相关文档块 |
| 4.4 | 实现 `rag/prompt_templates.py`：决策问答 prompt | — | prompt 模板字符串存在 |
| 4.5 | 实现 `rag_service.py`：整合实时数据 + 检索 + Claude | 4.3, 4.4, 3.9 | 给定问题返回结构化回答 |
| 4.6 | 实现 `POST /api/v1/chat/stream` SSE 接口 | 4.5 | curl 能收到流式 SSE 事件 |
| 4.7 | 前端：问答页面布局（对话列表 + 输入框） | Phase 2 | 页面能输入和显示消息 |
| 4.8 | 前端：SSE 流式接收 + 打字机效果 | 4.6, 4.7 | 回答逐字出现 |
| 4.9 | 前端：引用来源展示（来源标签 + 点击展开） | 4.8 | 回答下方显示引用来源 |
| 4.10 | 前端：预设快捷问题按钮（4-6 个） | 4.7 | 点击快捷按钮自动发送问题 |
| 4.11 | Prompt 调优：测试 5 类典型问题，迭代 prompt | 4.6 | 5 类问题回答质量合格（人工判断） |
| 4.12 | 测试：RAG 检索相关性 + 端到端问答 | 4.5 | `pytest tests/test_rag.py` 通过 |

### 5 类典型测试问题

1. 现状查询："科尔沁沙地当前植被覆盖状况如何？"
2. 风险评估："哪些区域沙化风险最高？"
3. 情景假设："增加杨树种植密度会有什么风险？"
4. 决策建议："本季度应优先治理哪些区域？"
5. 知识问答："三北防护林六期工程的目标是什么？"

### Phase 4 完成标志

- [ ] 问答页面能流式显示回答
- [ ] 回答中包含实时数据引用 + 文献引用
- [ ] 5 类测试问题回答质量通过人工审核

---

## Phase 5 — 预测 + 情景分析（2 周）

> **目标**：NDVI 未来趋势预测 + 造林方案情景模拟。

### 任务

| # | 任务 | 前置 | 验收标准 |
|---|------|------|---------|
| 5.1 | Prophet 基线预测：NDVI 未来 96 天（6 期） | Phase 1 数据 | 输出含 yhat + 置信区间 |
| 5.2 | API：`GET /api/v1/prediction/ndvi-forecast` | 5.1 | curl 返回预测 JSON |
| 5.3 | 前端：预测曲线（历史实线 + 预测虚线 + 置信区间） | 5.2, Phase 2 | 图表显示预测趋势 |
| 5.4 | 情景分析函数：`scenario_analysis_afforestation` | Phase 3 指标函数 | 输出各年度生态指标变化 |
| 5.5 | API：`POST /api/v1/prediction/scenario` | 5.4 | curl 返回情景分析 JSON |
| 5.6 | 前端：情景分析交互面板（树种/密度/年限选择 → 结果图） | 5.5 | 用户调参数，图表实时更新 |
| 5.7 | （可选）LSTM 训练：如有充足数据，训练深度预测模型 | 3 年+ 数据 | 预测精度优于 Prophet |
| 5.8 | 测试：预测结果合理性验证 | 5.1, 5.4 | 预测值在合理范围内 |

### Phase 5 完成标志

- [ ] 前端显示 NDVI 预测曲线
- [ ] 用户可选择树种和密度进行情景分析
- [ ] 情景分析结果包含风险预警和建议

---

## 后续扩展（不在当前计划内，按需启动）

以下功能在核心系统跑通后按优先级推进：

| 优先级 | 功能 | 触发条件 |
|--------|------|---------|
| P1 | 扩展区域：毛乌素沙地、塔克拉玛干南缘、黄土高原 | Phase 2 完成 |
| P1 | Sentinel-2 10m 高分辨率 NDVI（重点区域） | GEE 账号可用 |
| P2 | 用户认证（JWT）+ 多用户 | 需要给他人使用时 |
| P2 | 造林树种推荐（基于降水 + 土壤 + 立地） | Phase 5 完成 |
| P3 | 困难立地分级专题分析 | 有对应数据时 |
| P3 | 部署到云服务器 + Nginx + HTTPS | 需要公网访问时 |
| P3 | ChromaDB → Qdrant 迁移 | 向量库数据量 > 10万 |

---

## 风险清单与缓解措施

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| GEE 账号审批延迟 | Phase 1 阻塞 | 中 | **立即行动**：提交申请后同步准备 NESDC 离线数据降级路径 |
| ERA5 下载速度慢 | 数据入库慢 | 高 | 改用 GEE 上的 ERA5-Land 产品（带宽更好），或先用小区域数据 |
| TimescaleDB conda 安装失败 | 环境搭建受阻 | 低 | 退回普通 PostgreSQL + 手动分区，或用 Homebrew 单独安装 TimescaleDB |
| RAG 回答质量差 | Phase 4 质量不达标 | 中 | 增加语料量 + 调优 chunk_size + 迭代 prompt + 加入 few-shot 示例 |
| LSTM 数据不足 | Phase 5 精度差 | 中 | Prophet 作为长期基线方案即可，LSTM 标为可选 |
| GEE 免费配额不够 | 大区域请求失败 | 低 | 分块请求 + 降分辨率 + Prefect 加指数退避重试 |

---

## 数据源快速参考

| 数据 | 来源 | 访问 | 优先级 |
|------|------|------|--------|
| MODIS NDVI (500m, 16天) | GEE `MODIS/061/MOD13A1` | GEE API | 核心 |
| MODIS LST (1km, 8天) | GEE `MODIS/061/MOD11A2` | GEE API | 核心 |
| SMAP 土壤水分 (11km, 日) | GEE `NASA/SMAP/SPL4SMGP/007` | GEE API | 核心 |
| ERA5 气象 (0.25deg, 时) | CDS / GEE ERA5-Land | CDS API | 核心 |
| 三北工程区边界 (矢量) | NESDC | 下载 | 核心 |
| Sentinel-2 NDVI (10m, 5天) | GEE | GEE API | 扩展 |
| 中国人工林分布 (30m) | NESDC | 下载 | 扩展 |

---

## RAG 语料优先级

| 优先级 | 文献 | 来源 |
|--------|------|------|
| **必须** | 三北防护林体系建设工程总体规划（第六期） | 国家林草局 |
| **必须** | GB/T 15776 造林技术规程 | 国家标准 |
| **必须** | GB/T 21141 防沙治沙技术规范 | 国家标准 |
| **必须** | 三北工程40年评估报告（2019） | 中国林科院 |
| **必须** | 中国荒漠化和沙化状况公报（最新期） | 国家林草局 |
| 推荐 | 干旱半干旱区人工林适宜密度研究系列论文 | 期刊 |
| 推荐 | 三北地区主要造林树种耗水量研究 | 期刊 |
| 推荐 | 困难立地造林技术手册 | 林业出版社 |
| 推荐 | 沙漠化评价指标体系技术指南 | UNCCD/FAO |
| 推荐 | 中国北方防风固沙功能评估 | 生态学报 |

---

## 日常开发启动命令

```bash
# 终端 1：数据库 + 缓存
conda activate sandbelt
pg_ctl -D $CONDA_PREFIX/var/postgresql start
redis-server --daemonize yes

# 终端 2：后端
conda activate sandbelt && cd backend
uvicorn app.main:app --reload --port 8000

# 终端 3：前端
conda activate sandbelt && cd frontend
npm run dev

# 停止
pg_ctl -D $CONDA_PREFIX/var/postgresql stop
redis-cli shutdown
```

---

## API 端点速查

| 方法 | 路径 | 用途 | Phase |
|------|------|------|-------|
| GET | `/health` | 健康检查 | 0 |
| GET | `/api/v1/gis/regions` | 区域 GeoJSON | 2 |
| GET | `/api/v1/ecological/timeseries` | 生态指标时序 | 1 |
| GET | `/api/v1/ecological/current-status` | 区域综合状态 | 3 |
| GET | `/api/v1/prediction/ndvi-forecast` | NDVI 预测 | 5 |
| POST | `/api/v1/prediction/scenario` | 情景分析 | 5 |
| POST | `/api/v1/chat/stream` | RAG 问答 (SSE) | 4 |

---

*版本：v2.0 | 更新日期：2026-04-16*
*完整架构、Schema、代码模板详见 `docs/ARCHITECTURE.md`*

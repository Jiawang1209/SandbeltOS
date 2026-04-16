# 三北防护林智慧生态决策支持系统 — 项目计划书
## SandbeltOS — Smart Ecological Decision Support System for the Three-North Shelterbelt Program

> **定位**：面向三北防护林工程区的全栈生态智能平台，集实时遥感数据采集、生态指标计算、预测预警、RAG 智慧问答、GIS 可视化于一体，工程导向，完全依赖开放数据。

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构总览](#2-系统架构总览)
3. [技术栈选型](#3-技术栈选型)
4. [目录结构](#4-目录结构)
5. [数据层设计](#5-数据层设计)
6. [后端服务设计](#6-后端服务设计)
7. [RAG 知识库设计](#7-rag-知识库设计)
8. [前端设计](#8-前端设计)
9. [分阶段开发计划](#9-分阶段开发计划)
10. [环境配置与部署](#10-环境配置与部署)
11. [API 接口规范](#11-api-接口规范)
12. [数据源清单](#12-数据源清单)
13. [核心算法说明](#13-核心算法说明)
14. [注意事项与风险](#14-注意事项与风险)

---

## 1. 项目概述

### 1.1 背景

三北防护林工程（1978—2050）横跨东北、华北、西北13省，总面积约406万平方公里，是全球最大的人工防护林体系。当前面临的核心挑战包括：

- **水分超载**：部分区域人工林密度超过土壤水分承载力，出现"小老树"退化现象
- **沙化反弹**：蒙古高原气候变化导致沙尘源区扩张，防沙效果受到挑战
- **困难立地**：极端干旱、盐碱、沙地等困难立地造林成活率低
- **缺乏动态监测**：传统林业调查周期长，无法实时掌握生态系统状态

### 1.2 目标

构建一个**工程导向的全栈平台**，具备以下核心能力：

1. **实时监测**：自动从 GEE、ERA5 等开放数据源拉取植被、气象、土壤遥感数据
2. **生态评估**：计算 NDVI、植被覆盖度、防风固沙量、碳汇量等关键指标
3. **智能预测**：基于时序模型预测未来植被动态和沙化风险
4. **RAG 问答**：用户可用自然语言提问，系统结合实时数据+专业文献给出决策建议
5. **GIS 可视化**：交互式地图展示各类生态指标的空间分布和时序变化

### 1.3 目标用户

- 三北局及省级林草局的工程管理人员
- 生态修复工程师和决策支持需求者
- 生态学研究人员（数据分析和论文支撑）

### 1.4 核心功能示例

用户在问答框输入：
> "当前科尔沁沙地的土壤水分状况如何？如果未来5年继续增加杨树种植密度，会有什么风险？"

系统流程：
1. 从数据库检索该区域最新土壤水分、NDVI、降水亏缺指标
2. 从向量知识库检索"科尔沁造林密度"、"杨树耗水量"相关文献段落
3. 将数据上下文 + 文献上下文 + 用户问题组合为 prompt
4. 调用 Claude API 生成结构化回答，附引用来源
5. 前端流式展示回答，并联动地图高亮对应区域

---

## 2. 系统架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Next.js)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  GIS 地图面板  │  │  指标仪表盘   │  │  RAG 问答界面     │  │
│  │ Deck.gl+Mapbox│  │   ECharts    │  │  流式输出 + 引用  │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
└─────────┼─────────────────┼───────────────────┼────────────┘
          │                 │                   │
          ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                   后端 API (FastAPI)                         │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────────────┐ │
│  │ GIS 服务   │  │ 生态分析服务 │  │   RAG 问答引擎        │ │
│  │ PostGIS    │  │ 指标计算/预测│  │ LangChain + Claude   │ │
│  └────────────┘  └─────────────┘  └──────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌─────────────────┐ ┌──────────────┐ ┌───────────────────┐
│  TimescaleDB    │ │  ChromaDB    │ │   数据采集管道     │
│  时序生态指标    │ │  向量知识库   │ │  Prefect + GEE   │
│  PostGIS 空间   │ │  RAG 语料    │ │  ERA5 / NESDC    │
└─────────────────┘ └──────────────┘ └───────────────────┘
          ▲                                  │
          └──────────────────────────────────┘
                      自动写入
```

---

## 3. 技术栈选型

### 3.1 后端

| 组件 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| Web 框架 | FastAPI | ≥0.110 | REST API + SSE 流式输出 |
| ORM | SQLAlchemy | ≥2.0 | 数据库操作 |
| 时序数据库 | TimescaleDB (PostgreSQL) | ≥2.14 | 生态指标时序存储 |
| 空间扩展 | PostGIS | ≥3.4 | 矢量空间查询 |
| 向量数据库 | ChromaDB | ≥0.5 | RAG 文献检索 |
| RAG 框架 | LangChain | ≥0.2 | 问答链编排 |
| LLM API | Anthropic Claude | claude-sonnet-4-6 | 问答生成 |
| Embedding | text-embedding-3-small (OpenAI) 或 bge-m3 (本地) | — | 文献向量化 |
| 数据调度 | Prefect | ≥2.0 | 定时拉取遥感数据 |
| 遥感数据 | earthengine-api | ≥0.1.4 | GEE Python 接口 |
| 气象数据 | cdsapi | ≥0.7 | ERA5 下载 |
| 地理计算 | GeoPandas + Rasterio | — | 空间数据处理 |
| 缓存 | Redis | ≥7 | API 响应缓存 |
| 容器化 | Docker + Docker Compose | — | 本地和生产部署 |

### 3.2 前端

| 组件 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| 框架 | Next.js (React) | ≥14 | 全栈前端 |
| 地图引擎 | Deck.gl + MapboxGL / Maplibre | — | GIS 可视化 |
| 图表库 | ECharts | ≥5 | 时序图/雷达图/热力图 |
| 状态管理 | Zustand | — | 全局状态 |
| HTTP 客户端 | SWR + fetch | — | 数据请求 + SSE |
| UI 组件 | Shadcn/ui + Tailwind CSS | — | 界面组件 |
| 类型系统 | TypeScript | — | 类型安全 |

### 3.3 ML / 分析

| 组件 | 用途 |
|------|------|
| scikit-learn | 随机森林沙化风险分类 |
| PyTorch + LSTM | 植被 NDVI 时序预测 |
| Prophet | 快速时序基线预测 |
| InVEST (natcap) | 防风固沙服务量化 |
| RWEQ 模型 (自实现) | 风蚀模数计算 |

---

## 4. 目录结构

```
sandbelt-platform/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── config.py                # 环境变量配置
│   │   ├── database.py              # DB 连接池
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── ecological.py    # 生态指标接口
│   │   │   │   ├── gis.py           # 空间查询接口
│   │   │   │   ├── prediction.py    # 预测接口
│   │   │   │   └── chat.py          # RAG 问答接口（SSE）
│   │   ├── services/
│   │   │   ├── gee_service.py       # GEE 数据拉取
│   │   │   ├── era5_service.py      # ERA5 气象数据
│   │   │   ├── indicator_service.py # 生态指标计算
│   │   │   ├── prediction_service.py# 预测模型
│   │   │   ├── rag_service.py       # RAG 检索 + 问答
│   │   │   └── alert_service.py     # 预警逻辑
│   │   ├── models/
│   │   │   ├── orm.py               # SQLAlchemy ORM 模型
│   │   │   └── schemas.py           # Pydantic 请求/响应模型
│   │   └── utils/
│   │       ├── spatial.py           # 空间工具函数
│   │       └── time_utils.py        # 时间处理工具
│   ├── pipeline/
│   │   ├── flows/
│   │   │   ├── gee_ndvi_flow.py     # NDVI 定时拉取 flow
│   │   │   ├── era5_flow.py         # ERA5 定时拉取 flow
│   │   │   └── indicator_flow.py    # 指标计算 flow
│   │   └── prefect_deploy.py        # Prefect 部署配置
│   ├── rag/
│   │   ├── ingest.py                # 文献切片 + 向量化入库
│   │   ├── retriever.py             # 检索器封装
│   │   ├── prompt_templates.py      # Prompt 模板
│   │   └── docs/                    # 待入库的文献 PDF/txt
│   ├── ml/
│   │   ├── lstm_train.py            # LSTM 训练脚本
│   │   ├── lstm_predict.py          # LSTM 推理
│   │   ├── risk_classifier.py       # 沙化风险随机森林
│   │   └── models/                  # 训练好的模型文件
│   ├── tests/
│   │   ├── test_gee.py
│   │   ├── test_rag.py
│   │   └── test_indicators.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx                 # 主页（地图 + 仪表盘）
│   │   ├── chat/page.tsx            # 问答页
│   │   └── layout.tsx
│   ├── components/
│   │   ├── map/
│   │   │   ├── EcoMap.tsx           # Deck.gl 主地图
│   │   │   ├── NDVILayer.tsx        # NDVI 热力图层
│   │   │   ├── RiskLayer.tsx        # 沙化风险图层
│   │   │   └── WindLayer.tsx        # 风场图层
│   │   ├── dashboard/
│   │   │   ├── NDVIChart.tsx        # NDVI 时序图
│   │   │   ├── RiskGauge.tsx        # 风险仪表盘
│   │   │   ├── CarbonCard.tsx       # 碳汇卡片
│   │   │   └── AlertPanel.tsx       # 预警面板
│   │   └── chat/
│   │       ├── ChatWindow.tsx       # 问答窗口
│   │       ├── MessageBubble.tsx    # 消息气泡（含引用）
│   │       └── StreamingText.tsx    # 流式打字效果
│   ├── lib/
│   │   ├── api.ts                   # API 请求封装
│   │   └── sse.ts                   # SSE 流式接收
│   ├── store/
│   │   └── useEcoStore.ts           # Zustand 全局状态
│   └── package.json
│
├── data/
│   ├── boundaries/                  # 三北工程区矢量边界
│   ├── sample/                      # 测试用小样本数据
│   └── rag_docs/                    # RAG 语料文献
│
├── docker-compose.yml               # 本地开发全套服务
├── .env.example                     # 环境变量模板
└── README.md
```

---

## 5. 数据层设计

### 5.1 数据库 Schema（TimescaleDB + PostGIS）

```sql
-- 区域信息表（矢量）
CREATE TABLE regions (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,       -- 如"科尔沁沙地"
    level       VARCHAR(20),                 -- province / subregion / plot
    geom        GEOMETRY(MULTIPOLYGON, 4326),
    area_km2    FLOAT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_regions_geom ON regions USING GIST(geom);

-- 生态指标时序表（超表，TimescaleDB）
CREATE TABLE eco_indicators (
    time        TIMESTAMPTZ NOT NULL,
    region_id   INTEGER REFERENCES regions(id),
    indicator   VARCHAR(50) NOT NULL,  -- 'ndvi','evi','lst','fvc','soil_moisture'
    value       FLOAT NOT NULL,
    source      VARCHAR(30),           -- 'MODIS','Sentinel2','ERA5','SMAP'
    resolution  VARCHAR(20),           -- '250m','10m','0.25deg'
    quality     SMALLINT DEFAULT 1     -- 0=poor,1=ok,2=good
);
SELECT create_hypertable('eco_indicators','time');
CREATE INDEX idx_eco_region_indicator ON eco_indicators(region_id, indicator, time DESC);

-- 气象数据时序表
CREATE TABLE weather_data (
    time            TIMESTAMPTZ NOT NULL,
    region_id       INTEGER REFERENCES regions(id),
    precipitation   FLOAT,   -- mm/day
    wind_speed      FLOAT,   -- m/s
    wind_direction  FLOAT,   -- degrees
    temperature     FLOAT,   -- Celsius
    evapotranspiration FLOAT, -- mm/day
    soil_moisture   FLOAT    -- m3/m3
);
SELECT create_hypertable('weather_data','time');

-- 沙化风险评估记录
CREATE TABLE desertification_risk (
    time        TIMESTAMPTZ NOT NULL,
    region_id   INTEGER REFERENCES regions(id),
    risk_level  SMALLINT,    -- 1=低,2=中,3=高,4=极高
    risk_score  FLOAT,       -- 0~1
    wind_erosion_modulus FLOAT,  -- t/(km²·a)
    sand_fixation_amount FLOAT,  -- t/(km²·a)
    factors     JSONB        -- 贡献因子分解
);
SELECT create_hypertable('desertification_risk','time');

-- 造林记录表
CREATE TABLE afforestation_records (
    id          SERIAL PRIMARY KEY,
    region_id   INTEGER REFERENCES regions(id),
    year        INTEGER,
    species     VARCHAR(100),    -- 树种
    area_ha     FLOAT,           -- 造林面积（公顷）
    density     INTEGER,         -- 株/公顷
    survival_rate FLOAT,         -- 成活率
    source      VARCHAR(50)      -- 数据来源
);

-- 预警记录表
CREATE TABLE alerts (
    id          SERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    region_id   INTEGER REFERENCES regions(id),
    alert_type  VARCHAR(50),  -- 'desertification','drought','vegetation_decline'
    severity    VARCHAR(20),  -- 'info','warning','critical'
    message     TEXT,
    is_read     BOOLEAN DEFAULT FALSE
);
```

### 5.2 数据采集流程

#### GEE NDVI 拉取（每 16 天自动执行）

```python
# backend/services/gee_service.py
import ee
import pandas as pd
from datetime import datetime, timedelta

def fetch_modis_ndvi(region_geom: dict, start_date: str, end_date: str) -> pd.DataFrame:
    """
    从 GEE 拉取 MODIS MOD13A1 16天合成 NDVI
    region_geom: GeoJSON geometry (三北工程区或子区域)
    返回: DataFrame(time, region_id, ndvi_mean, ndvi_min, ndvi_max)
    """
    ee.Initialize()
    
    roi = ee.Geometry(region_geom)
    
    collection = (
        ee.ImageCollection('MODIS/061/MOD13A1')
        .filterDate(start_date, end_date)
        .filterBounds(roi)
        .select(['NDVI', 'EVI', 'SummaryQA'])
    )
    
    def extract_stats(image):
        date = image.date().format('YYYY-MM-dd')
        ndvi = image.select('NDVI').multiply(0.0001)  # scale factor
        evi  = image.select('EVI').multiply(0.0001)
        
        stats = ndvi.reduceRegion(
            reducer=ee.Reducer.mean().combine(
                ee.Reducer.min(), sharedInputs=True
            ).combine(
                ee.Reducer.max(), sharedInputs=True
            ),
            geometry=roi,
            scale=500,
            maxPixels=1e13
        )
        return ee.Feature(None, stats.set('date', date))
    
    features = collection.map(extract_stats)
    result = features.getInfo()
    
    rows = []
    for feat in result['features']:
        p = feat['properties']
        rows.append({
            'time': p['date'],
            'ndvi_mean': p.get('NDVI_mean'),
            'ndvi_min':  p.get('NDVI_min'),
            'ndvi_max':  p.get('NDVI_max'),
            'evi_mean':  p.get('EVI_mean'),
        })
    return pd.DataFrame(rows)


def fetch_modis_lst(region_geom: dict, start_date: str, end_date: str) -> pd.DataFrame:
    """拉取 MOD11A2 地表温度（8天合成）"""
    ee.Initialize()
    roi = ee.Geometry(region_geom)
    
    collection = (
        ee.ImageCollection('MODIS/061/MOD11A2')
        .filterDate(start_date, end_date)
        .filterBounds(roi)
        .select(['LST_Day_1km'])
    )
    
    def extract(image):
        lst_k = image.select('LST_Day_1km').multiply(0.02)  # Kelvin
        lst_c = lst_k.subtract(273.15)
        stats = lst_c.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=1000,
            maxPixels=1e13
        )
        return ee.Feature(None, stats.set('date', image.date().format('YYYY-MM-dd')))
    
    result = collection.map(extract).getInfo()
    rows = [{'time': f['properties']['date'], 
             'lst_mean': f['properties'].get('LST_Day_1km_mean')} 
            for f in result['features']]
    return pd.DataFrame(rows)


def fetch_smap_soil_moisture(region_geom: dict, start_date: str, end_date: str) -> pd.DataFrame:
    """拉取 SMAP L4 土壤含水量（每日）"""
    ee.Initialize()
    roi = ee.Geometry(region_geom)
    
    collection = (
        ee.ImageCollection('NASA/SMAP/SPL4SMGP/007')
        .filterDate(start_date, end_date)
        .filterBounds(roi)
        .select(['sm_surface'])
    )
    
    def extract(image):
        stats = image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=11000,
            maxPixels=1e13
        )
        return ee.Feature(None, stats.set('date', image.date().format('YYYY-MM-dd')))
    
    result = collection.map(extract).getInfo()
    rows = [{'time': f['properties']['date'],
             'soil_moisture': f['properties'].get('sm_surface_mean')}
            for f in result['features']]
    return pd.DataFrame(rows)
```

#### ERA5 气象数据拉取（每日执行）

```python
# backend/services/era5_service.py
import cdsapi
import xarray as xr
import pandas as pd

ERA5_VARIABLES = [
    'total_precipitation',
    '10m_u_component_of_wind',
    '10m_v_component_of_wind',
    '2m_temperature',
    'potential_evaporation',
]

def fetch_era5_daily(year: int, month: int, bbox: list) -> pd.DataFrame:
    """
    bbox: [north, west, south, east] (三北区域约 [55, 73, 35, 135])
    返回: DataFrame with daily weather stats per region
    """
    c = cdsapi.Client()
    
    output_path = f'/tmp/era5_{year}_{month:02d}.nc'
    
    c.retrieve(
        'reanalysis-era5-single-levels',
        {
            'product_type': 'reanalysis',
            'variable': ERA5_VARIABLES,
            'year': str(year),
            'month': f'{month:02d}',
            'day': [f'{d:02d}' for d in range(1, 32)],
            'time': ['00:00', '06:00', '12:00', '18:00'],
            'area': bbox,
            'format': 'netcdf',
        },
        output_path
    )
    
    ds = xr.open_dataset(output_path)
    df = ds.to_dataframe().reset_index()
    
    # 日聚合：降水累积，风速/温度取均值
    df['wind_speed'] = (df['u10']**2 + df['v10']**2) ** 0.5
    df['wind_direction'] = (180 + (180/3.14159) * 
                            pd.np.arctan2(df['u10'], df['v10'])) % 360
    
    daily = df.groupby(['latitude', 'longitude', df['time'].dt.date]).agg(
        precipitation=('tp', 'sum'),
        temperature=('t2m', 'mean'),
        wind_speed=('wind_speed', 'mean'),
        wind_direction=('wind_direction', 'mean'),
    ).reset_index()
    
    return daily
```

---

## 6. 后端服务设计

### 6.1 FastAPI 主入口

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import ecological, gis, prediction, chat

app = FastAPI(
    title="三北防护林智慧生态决策支持系统 API",
    version="1.0.0",
    description="Three-North Shelterbelt Smart Ecological Decision Support Platform"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ecological.router, prefix="/api/v1/ecological", tags=["生态指标"])
app.include_router(gis.router,        prefix="/api/v1/gis",        tags=["GIS空间"])
app.include_router(prediction.router, prefix="/api/v1/prediction", tags=["预测预警"])
app.include_router(chat.router,       prefix="/api/v1/chat",       tags=["RAG问答"])
```

### 6.2 生态指标服务

```python
# backend/services/indicator_service.py
import numpy as np
from typing import Optional

def calculate_fvc(ndvi: float, ndvi_soil: float = 0.05, ndvi_veg: float = 0.85) -> float:
    """
    像元二分模型计算植被覆盖度 FVC (Fractional Vegetation Cover)
    ndvi_soil: 裸地NDVI（三北干旱区取0.02~0.05）
    ndvi_veg:  纯植被NDVI（三北区取0.80~0.90）
    """
    fvc = (ndvi - ndvi_soil) / (ndvi_veg - ndvi_soil)
    return float(np.clip(fvc, 0, 1))


def calculate_wind_erosion_modulus(
    wind_speed: float,
    fvc: float,
    soil_crust_factor: float = 1.0,
    rainfall: float = 0.0
) -> float:
    """
    基于修正风蚀方程 RWEQ 的简化风蚀模数估算
    wind_speed: m/s（月均或季均）
    fvc: 植被覆盖度 0~1
    soil_crust_factor: 结皮因子（有结皮=0.3，无=1.0）
    rainfall: 月降水量 mm
    返回: 风蚀模数 t/(km²·month)
    """
    # 植被覆盖抑制因子
    vegetation_factor = np.exp(-3.0 * fvc)
    
    # 风速因子（阈值摩擦速度约5.5 m/s对应临界起沙风速~10m/s）
    threshold = 5.5
    if wind_speed <= threshold:
        return 0.0
    wind_factor = (wind_speed - threshold) ** 3
    
    # 降水抑制因子
    rain_factor = np.exp(-0.05 * rainfall)
    
    modulus = wind_factor * vegetation_factor * soil_crust_factor * rain_factor * 0.18
    return max(0.0, float(modulus))


def calculate_sand_fixation_service(
    actual_erosion: float,
    potential_erosion_no_vegetation: float
) -> float:
    """
    防风固沙服务量 = 潜在风蚀量（无植被） - 实际风蚀量
    单位: t/(km²·month)
    """
    return max(0.0, potential_erosion_no_vegetation - actual_erosion)


def estimate_carbon_density(ndvi: float, vegetation_type: str = 'mixed') -> float:
    """
    基于NDVI的地上生物量碳密度快速估算
    vegetation_type: 'shrub','tree','grass','mixed'
    返回: gC/m²
    """
    coefficients = {
        'tree':  {'a': 78.5, 'b': 2.1},
        'shrub': {'a': 42.3, 'b': 1.8},
        'grass': {'a': 25.0, 'b': 1.5},
        'mixed': {'a': 55.0, 'b': 1.9},
    }
    c = coefficients.get(vegetation_type, coefficients['mixed'])
    agb = c['a'] * (ndvi ** c['b'])  # g/m²
    carbon = agb * 0.47              # 碳转换系数
    return float(max(0.0, carbon))


def assess_desertification_risk(
    fvc: float,
    wind_erosion_modulus: float,
    soil_moisture: float,
    precipitation_anomaly: float  # 当月降水相比多年均值的百分比偏差
) -> dict:
    """
    综合沙化风险评估
    返回: {'risk_level': 1-4, 'risk_score': 0-1, 'factors': {...}}
    """
    # 各因子归一化评分（越高越危险）
    fvc_score      = max(0, 1 - fvc / 0.3)      # FVC<30%时高风险
    erosion_score  = min(1, wind_erosion_modulus / 500)
    moisture_score = max(0, 1 - soil_moisture / 0.15)
    drought_score  = max(0, -precipitation_anomaly / 50)  # 降水偏少时高
    
    # 加权综合
    weights = {'fvc': 0.35, 'erosion': 0.30, 'moisture': 0.20, 'drought': 0.15}
    risk_score = (
        weights['fvc']      * fvc_score +
        weights['erosion']  * erosion_score +
        weights['moisture'] * moisture_score +
        weights['drought']  * drought_score
    )
    
    if risk_score < 0.25:   risk_level = 1  # 低风险
    elif risk_score < 0.50: risk_level = 2  # 中风险
    elif risk_score < 0.75: risk_level = 3  # 高风险
    else:                   risk_level = 4  # 极高风险
    
    return {
        'risk_level': risk_level,
        'risk_score': round(risk_score, 3),
        'factors': {
            'vegetation_cover': round(fvc_score, 3),
            'wind_erosion':     round(erosion_score, 3),
            'soil_moisture':    round(moisture_score, 3),
            'drought_anomaly':  round(drought_score, 3),
        }
    }
```

### 6.3 预测服务

```python
# backend/services/prediction_service.py
"""
LSTM 时序预测：给定过去 N 个时间步的 NDVI 序列，预测未来 M 步。
Prophet 作为快速基线（不需要训练，适合冷启动阶段）。
"""
import torch
import torch.nn as nn
import numpy as np
from prophet import Prophet
import pandas as pd


class LSTMPredictor(nn.Module):
    """
    单变量/多变量 LSTM，用于 NDVI 时序预测
    输入: (batch, seq_len, input_size)  -- input_size=1(仅NDVI)或更多
    输出: (batch, pred_steps)
    """
    def __init__(self, input_size=1, hidden_size=64, num_layers=2, pred_steps=6):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, 
                            batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden_size, pred_steps)
    
    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


def predict_ndvi_prophet(
    historical: pd.DataFrame,  # columns: ds(datetime), y(ndvi)
    periods: int = 6,           # 预测未来期数（16天步长则6步=96天≈3个月）
    freq: str = '16D'
) -> pd.DataFrame:
    """
    用 Prophet 快速预测 NDVI，支持季节性分解
    返回 DataFrame: ds, yhat, yhat_lower, yhat_upper
    """
    m = Prophet(
        seasonality_mode='multiplicative',
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
    )
    m.fit(historical)
    future = m.make_future_dataframe(periods=periods, freq=freq)
    forecast = m.predict(future)
    return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(periods)


def scenario_analysis_afforestation(
    current_fvc: float,
    current_soil_moisture: float,
    precipitation_mean: float,     # mm/year
    additional_density: int,        # 额外增加的造林密度 株/公顷
    species: str = 'poplar',        # 树种
    years: int = 5
) -> dict:
    """
    情景分析：增加人工造林密度对生态系统的影响模拟
    返回: 各年度预测的生态指标变化
    
    基于以下生态学关系：
    - 每公顷杨树年耗水量约 600~900mm（视立地条件）
    - 三北干旱区年降水量 200~450mm
    - 当树木耗水量 > 降水补给时，土壤水分持续下降，
      导致"小老树"效应（FVC 下降、生长停滞）
    """
    SPECIES_WATER_USE = {
        'poplar':  750,    # 杨树 mm/year
        'willow':  700,
        'pine':    450,
        'elm':     380,
        'seabuckthorn': 300,
        'caragana':     200,  # 柠条，耐旱灌木
    }
    
    water_use_per_tree = SPECIES_WATER_USE.get(species, 500) / 10000  # mm·ha/株 → mm/株
    total_water_demand_increase = additional_density * water_use_per_tree  # mm/year
    
    results = []
    sm = current_soil_moisture
    fvc = current_fvc
    
    for year in range(1, years + 1):
        # 水分亏缺判断
        water_deficit = total_water_demand_increase - (precipitation_mean * 0.3)
        if water_deficit > 0:
            sm = max(0.02, sm - water_deficit * 0.001)
            # 土壤水分不足时 FVC 下降
            stress_factor = max(0, (sm - 0.04) / (0.15 - 0.04))
            fvc = max(0.02, fvc * (0.95 + 0.05 * stress_factor))
        else:
            # 水分充足，造林初期 FVC 略有提升
            fvc = min(0.95, fvc * 1.02)
        
        risk = assess_desertification_risk(
            fvc=fvc,
            wind_erosion_modulus=calculate_wind_erosion_modulus(
                wind_speed=6.0, fvc=fvc, rainfall=precipitation_mean/12
            ),
            soil_moisture=sm,
            precipitation_anomaly=0
        )
        
        results.append({
            'year': year,
            'fvc': round(fvc, 3),
            'soil_moisture': round(sm, 4),
            'water_deficit_mm': round(max(0, water_deficit), 1),
            'risk_level': risk['risk_level'],
            'risk_score': risk['risk_score'],
            'warning': '土壤水分严重不足，建议减少密度或改换耐旱树种' 
                       if sm < 0.05 else None
        })
    
    return {
        'scenario': {
            'species': species,
            'additional_density_per_ha': additional_density,
            'years': years,
        },
        'yearly_projection': results,
        'recommendation': _generate_recommendation(results, species, precipitation_mean)
    }


def _generate_recommendation(results: list, species: str, precip: float) -> str:
    final = results[-1]
    if final['risk_level'] >= 3:
        return (f"⚠️ 高风险预警：在年降水量{precip:.0f}mm的区域大量种植{species}，"
                f"5年后沙化风险将达{['低','中','高','极高'][final['risk_level']-1]}级。"
                f"建议：降低种植密度至≤300株/公顷，或替换为柠条、沙棘等耐旱灌木。")
    elif final['risk_level'] == 2:
        return f"中等风险：建议密切监测土壤水分，控制种植密度，优先选择乡土耐旱树种。"
    else:
        return f"当前方案风险可控，建议持续监测NDVI和土壤水分变化。"
```

---

## 7. RAG 知识库设计

### 7.1 语料库构建

**初始语料清单（优先级排序）：**

| 文档 | 来源 | 优先级 |
|------|------|--------|
| 三北防护林体系建设工程总体规划（第六期） | 国家林草局 | ★★★ |
| GB/T 15776 造林技术规程 | 国家标准 | ★★★ |
| GB/T 21141 防沙治沙技术规范 | 国家标准 | ★★★ |
| 三北工程40年评估报告（2019，中国林科院） | 中国林科院 | ★★★ |
| 中国荒漠化和沙化状况公报（最新期） | 国家林草局 | ★★★ |
| 干旱半干旱区人工林适宜密度研究系列论文 | 期刊论文 | ★★☆ |
| 三北地区主要造林树种耗水量研究 | 期刊论文 | ★★☆ |
| 困难立地造林技术手册 | 林业出版社 | ★★☆ |
| 沙漠化评价指标体系技术指南 | UNCCD/FAO | ★★☆ |
| 中国北方防风固沙功能评估 | 生态学报系列 | ★★☆ |

### 7.2 RAG 服务实现

```python
# backend/rag/retriever.py
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_anthropic import ChatAnthropic
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
import os

# 使用 OpenAI embedding（或替换为本地 bge-m3）
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

CHROMA_PATH = "./chroma_db"

def build_knowledge_base(docs_dir: str = "./rag/docs"):
    """
    一次性构建向量知识库
    支持 PDF 和 TXT 格式
    """
    docs = []
    
    for fname in os.listdir(docs_dir):
        fpath = os.path.join(docs_dir, fname)
        if fname.endswith('.pdf'):
            loader = PyPDFLoader(fpath)
        elif fname.endswith('.txt'):
            loader = TextLoader(fpath, encoding='utf-8')
        else:
            continue
        docs.extend(loader.load())
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", "。", "；", " "],
    )
    chunks = splitter.split_documents(docs)
    
    print(f"共切分 {len(chunks)} 个文档块，开始向量化...")
    
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_PATH,
        collection_name="sandbelt_knowledge"
    )
    vectorstore.persist()
    print(f"知识库构建完成，存储于 {CHROMA_PATH}")
    return vectorstore


def load_knowledge_base():
    return Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings,
        collection_name="sandbelt_knowledge"
    )


# backend/rag/prompt_templates.py
ECO_DECISION_PROMPT = PromptTemplate(
    input_variables=["context", "eco_data", "question"],
    template="""你是一位专注于中国三北防护林工程的生态学专家和决策顾问。
请结合以下信息回答用户的问题：

## 实时生态数据（来自遥感监测）
{eco_data}

## 专业知识库检索结果
{context}

## 用户问题
{question}

## 回答要求
1. 优先基于实时生态数据给出针对当前区域状况的具体判断
2. 引用专业知识库中的依据支撑你的结论
3. 如涉及风险预警，明确指出风险等级（低/中/高/极高）
4. 提供具体可操作的决策建议（如造林密度范围、树种选择、时间窗口）
5. 如数据不足以支撑某个结论，明确说明不确定性
6. 使用中文回答，语言专业但清晰易懂

## 回答："""
)
```

### 7.3 问答 API（SSE 流式输出）

```python
# backend/app/api/v1/chat.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.rag_service import RagService
from services.indicator_service import get_region_latest_indicators
import json

router = APIRouter()

class ChatRequest(BaseModel):
    question: str
    region_id: int = 1        # 默认科尔沁沙地
    include_forecast: bool = True

async def event_stream(question: str, region_id: int):
    """
    SSE 流式生成 RAG 回答
    前端通过 EventSource 接收
    """
    # 1. 拉取实时生态数据
    eco_data = await get_region_latest_indicators(region_id)
    eco_context = format_eco_data_for_prompt(eco_data)
    
    # 2. RAG 检索
    rag = RagService()
    retrieved_docs = rag.retrieve(question, k=5)
    doc_context = "\n\n---\n\n".join([
        f"【来源：{d.metadata.get('source','未知')}】\n{d.page_content}"
        for d in retrieved_docs
    ])
    
    # 3. 调用 Claude API（流式）
    import anthropic
    client = anthropic.Anthropic()
    
    full_prompt = ECO_DECISION_PROMPT.format(
        eco_data=eco_context,
        context=doc_context,
        question=question
    )
    
    # 先发送引用来源
    sources = [{'source': d.metadata.get('source',''), 
                'page': d.metadata.get('page','')} 
               for d in retrieved_docs]
    yield f"data: {json.dumps({'type':'sources','data':sources}, ensure_ascii=False)}\n\n"
    
    # 流式发送回答
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": full_prompt}]
    ) as stream:
        for text in stream.text_stream:
            yield f"data: {json.dumps({'type':'token','data':text}, ensure_ascii=False)}\n\n"
    
    yield "data: [DONE]\n\n"


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    return StreamingResponse(
        event_stream(req.question, req.region_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


def format_eco_data_for_prompt(eco_data: dict) -> str:
    return f"""
区域：{eco_data.get('region_name', '未知')}
监测时间：{eco_data.get('latest_time', '未知')}
NDVI（植被指数）：{eco_data.get('ndvi_mean', 'N/A'):.3f}（{interpret_ndvi(eco_data.get('ndvi_mean'))}）
植被覆盖度（FVC）：{eco_data.get('fvc', 'N/A'):.1%}
土壤水分：{eco_data.get('soil_moisture', 'N/A'):.3f} m³/m³
月均降水：{eco_data.get('precipitation_monthly', 'N/A'):.1f} mm
当前沙化风险等级：{['低','中','高','极高'][eco_data.get('risk_level',1)-1]}
风蚀模数：{eco_data.get('wind_erosion_modulus', 'N/A'):.1f} t/(km²·月)
近3个月NDVI趋势：{eco_data.get('ndvi_trend', '稳定')}
"""

def interpret_ndvi(ndvi: float) -> str:
    if ndvi is None: return "数据缺失"
    if ndvi < 0.1:   return "极稀疏裸地"
    if ndvi < 0.2:   return "稀疏植被"
    if ndvi < 0.3:   return "低覆盖植被"
    if ndvi < 0.5:   return "中等植被"
    if ndvi < 0.7:   return "良好植被"
    return "茂密植被"
```

---

## 8. 前端设计

### 8.1 页面结构

**主页（/）— 生态监控大屏**
- 左侧：三北工程区 GIS 地图（Deck.gl）
  - 底图：Maplibre（开源，无需 token）或 Mapbox
  - 可切换图层：NDVI 热力图 / 沙化风险图 / 风场流线图 / 降水分布图
  - 点击区域弹出 Popup 显示该区域最新指标
- 右侧上：关键指标卡（NDVI 均值、FVC、高风险区面积、碳汇量）
- 右侧下：NDVI 时序折线图（含预测曲线）+ 风险趋势图
- 顶部：预警通知栏（红色/橙色闪烁预警）

**问答页（/chat）— 智慧决策助手**
- 左侧：问题历史列表
- 右侧主体：对话区
  - 用户气泡：深色背景
  - 助手回答：白色卡片，顶部显示引用来源（可点击展开文献片段）
  - 流式打字效果
  - 底部：输入框 + 发送按钮 + 区域选择下拉 + 预设问题快捷键
- 预设快捷问题示例：
  - "当前该区域沙化风险如何？"
  - "建议本季度优先处置哪些区块？"
  - "如果增加500株/公顷杨树，5年后会怎样？"
  - "哪些困难立地需要优先生态修复？"

### 8.2 关键前端代码

```typescript
// frontend/lib/sse.ts
export async function streamChat(
  question: string,
  regionId: number,
  onToken: (token: string) => void,
  onSources: (sources: any[]) => void,
  onDone: () => void
) {
  const response = await fetch('/api/v1/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, region_id: regionId }),
  });

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const lines = decoder.decode(value).split('\n');
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6);
      if (data === '[DONE]') { onDone(); return; }

      const parsed = JSON.parse(data);
      if (parsed.type === 'token')   onToken(parsed.data);
      if (parsed.type === 'sources') onSources(parsed.data);
    }
  }
}
```

```typescript
// frontend/components/map/NDVILayer.tsx
import { HeatmapLayer } from '@deck.gl/aggregation-layers';

export function createNDVILayer(data: any[]) {
  return new HeatmapLayer({
    id: 'ndvi-heatmap',
    data,
    getPosition: (d: any) => [d.longitude, d.latitude],
    getWeight: (d: any) => d.ndvi_mean,
    radiusPixels: 30,
    colorRange: [
      [255, 255, 204],   // 极低 NDVI（黄）
      [161, 218, 180],   // 低
      [65, 182, 196],    // 中低
      [44, 127, 184],    // 中
      [37, 52, 148],     // 高（深蓝绿）
    ],
    intensity: 1,
    threshold: 0.05,
  });
}
```

---

## 9. 分阶段开发计划

### Phase 1 — 数据管道 + 基础可视化（第 1~2 周）

**目标**：跑通从 GEE 拉数据到前端显示地图的完整链路

**任务清单：**
- [ ] 按 10.3 节完成 `sandbelt` conda 环境搭建（PostgreSQL + TimescaleDB + Redis + Node.js 全部通过 conda 安装）
- [ ] 实现 `gee_service.py`：拉取科尔沁沙地 2020—2024 年 MODIS NDVI
- [ ] 实现 `era5_service.py`：拉取对应区域同期气象数据
- [ ] 创建数据库 Schema，写入历史数据
- [ ] 实现 `/api/v1/ecological/timeseries` 接口
- [ ] 前端：Deck.gl 地图展示三北工程区边界 + NDVI 热力图
- [ ] 前端：ECharts NDVI 时序折线图
- [ ] 下载并导入三北工程区矢量边界（NESDC）

**验收标准**：能在浏览器地图上看到科尔沁沙地 2024 年近期 NDVI 分布热力图

---

### Phase 2 — 生态评估 + 预警（第 3~4 周）

**目标**：完成核心生态指标计算和预警功能

**任务清单：**
- [ ] 实现 `indicator_service.py` 全部函数（FVC、风蚀模数、固沙量、碳汇）
- [ ] 实现 Prefect 定时 flow（每 16 天自动拉 NDVI，每日拉气象）
- [ ] 实现 `prediction_service.py`：Prophet 基线预测 + LSTM 训练脚本
- [ ] 实现 `alert_service.py`：沙化风险超阈值自动写入 alerts 表
- [ ] 实现 `/api/v1/prediction/ndvi-forecast` 接口
- [ ] 前端：仪表盘 4 个指标卡 + 预警通知栏
- [ ] 前端：沙化风险等级地图图层（红/橙/黄/绿色分级）
- [ ] 前端：NDVI 预测曲线（历史实线 + 预测虚线 + 置信区间阴影）

**验收标准**：系统能自动识别高风险区域并在仪表盘显示预警

---

### Phase 3 — RAG 问答（第 5~6 周）

**目标**：完成智慧问答功能，能回答结合实时数据的决策问题

**任务清单：**
- [ ] 收集初始 RAG 语料（≥15 篇关键文献 + 3 个行业标准）
- [ ] 实现 `rag/ingest.py`：PDF 切片 + 向量化入 ChromaDB
- [ ] 实现 `rag/retriever.py` + `prompt_templates.py`
- [ ] 实现 `/api/v1/chat/stream` SSE 接口
- [ ] 实现 `scenario_analysis_afforestation` 函数
- [ ] 前端：完整问答界面（流式输出 + 引用来源展示）
- [ ] 前端：预设快捷问题按钮
- [ ] 测试 5 类典型问题的回答质量并调优 prompt

**验收标准**：用户输入"未来增加人工种植的影响"，系统能给出包含当前 NDVI 数据和文献依据的结构化回答

---

### Phase 4 — 完善与上线（第 7~8 周）

**任务清单：**
- [ ] 扩展区域覆盖：毛乌素沙地、塔克拉玛干南缘、黄土高原
- [ ] 接入 Sentinel-2 10m 高分辨率 NDVI（重点区域）
- [ ] 困难立地分级专题分析模块
- [ ] 造林树种推荐功能（基于降水量 + 土壤类型 + 立地条件）
- [ ] 用户认证（JWT）+ 多用户支持
- [ ] 部署到云服务器（阿里云 / 腾讯云 ECS）
- [ ] Nginx 反向代理 + HTTPS
- [ ] 接口性能优化（数据库索引、Redis 缓存热点查询）

---

## 10. 环境配置与部署

> **本项目完全基于 Miniforge 本地开发，不使用 Docker。** 所有服务（PostgreSQL、TimescaleDB、Redis、Python 后端、Node.js 前端）均通过 `conda` 在 `sandbelt` 环境内统一管理，零额外依赖。

### 10.1 Miniforge 环境搭建（一次性操作）

#### 第一步：创建 `sandbelt` 环境

```bash
# 创建环境，Python 3.11 兼容性最佳
conda create -n sandbelt python=3.11 -y
conda activate sandbelt
```

#### 第二步：通过 conda-forge 安装所有服务和底层库

```bash
# ① 数据库：PostgreSQL 16 + TimescaleDB + PostGIS
conda install -c conda-forge \
    postgresql=16 \
    timescaledb \
    postgis \
    -y

# ② 缓存：Redis
conda install -c conda-forge redis-server -y

# ③ 地理空间底层（必须 conda 装，pip 装容易编译失败）
conda install -c conda-forge \
    gdal rasterio geopandas shapely fiona pyproj \
    netcdf4 hdf5 \
    -y

# ④ PyTorch（macOS Apple Silicon 用 metal 加速，Intel 用 cpuonly）
conda install -c conda-forge pytorch cpuonly -y   # Intel Mac
# conda install -c pytorch pytorch -y             # Apple Silicon 改用此行

# ⑤ Node.js（前端构建）
conda install -c conda-forge nodejs=20 -y

# ⑥ 其余 Python 依赖（pip 安装）
pip install -r backend/requirements.txt

# ⑦ 前端依赖
cd frontend && npm install && cd ..
```

#### 第三步：初始化 PostgreSQL 数据库

```bash
conda activate sandbelt

# 初始化数据目录（仅首次）
initdb -D $CONDA_PREFIX/var/postgresql -U sandbelt --pwprompt
# 提示输入密码时设置：your_password_here

# 配置 TimescaleDB 扩展（将下面一行加入 postgresql.conf）
echo "shared_preload_libraries = 'timescaledb'" >> $CONDA_PREFIX/var/postgresql/postgresql.conf

# 启动 PostgreSQL
pg_ctl -D $CONDA_PREFIX/var/postgresql -l $CONDA_PREFIX/var/postgresql/logfile start

# 创建数据库
createdb -U sandbelt sandbelt_db

# 连接并启用扩展
psql -U sandbelt -d sandbelt_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
psql -U sandbelt -d sandbelt_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# 执行建表 SQL
psql -U sandbelt -d sandbelt_db -f backend/sql/init.sql
```

#### 第四步：配置 `.env`

```bash
cp .env.example .env
# 按实际情况填写下方配置
```

`.env.example` 内容：

```bash
# 数据库（本地 conda PostgreSQL）
POSTGRES_USER=sandbelt
POSTGRES_PASSWORD=your_password_here
POSTGRES_DB=sandbelt_db
DATABASE_URL=postgresql://sandbelt:your_password_here@localhost:5432/sandbelt_db

# Redis（本地 conda Redis）
REDIS_URL=redis://localhost:6379/0

# GEE（需提前在 https://code.earthengine.google.com 注册）
GEE_SERVICE_ACCOUNT=your-service-account@project.iam.gserviceaccount.com
GEE_KEY_FILE=./secrets/gee-key.json

# ERA5（需在 https://cds.climate.copernicus.eu 注册）
CDS_API_URL=https://cds.climate.copernicus.eu/api/v2
CDS_API_KEY=your_cds_api_key_here

# LLM
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here   # 用于 embedding

# Mapbox（可用 Maplibre 替代，则不需要此项）
NEXT_PUBLIC_MAPBOX_TOKEN=your_mapbox_token_here

# 应用
ENVIRONMENT=development
LOG_LEVEL=INFO
```

---

### 10.2 日常开发启动流程

每次开发时，按顺序在不同终端标签页执行：

```bash
# ── 标签页 1：激活环境，启动数据库和缓存 ──────────────────────────
conda activate sandbelt
pg_ctl -D $CONDA_PREFIX/var/postgresql start        # 启动 PostgreSQL
redis-server --daemonize yes                         # 启动 Redis（后台）

# ── 标签页 2：启动后端 API ────────────────────────────────────────
conda activate sandbelt
cd sandbelt-platform/backend
uvicorn app.main:app --reload --port 8000

# ── 标签页 3：启动前端 ───────────────────────────────────────────
conda activate sandbelt
cd sandbelt-platform/frontend
npm run dev                                          # 访问 http://localhost:3000

# ── 标签页 4（可选）：启动 Prefect 调度 ─────────────────────────
conda activate sandbelt
cd sandbelt-platform/backend
python pipeline/prefect_deploy.py
```

**停止所有服务：**

```bash
conda activate sandbelt
pg_ctl -D $CONDA_PREFIX/var/postgresql stop
redis-cli shutdown
# 其余进程 Ctrl+C 结束
```

---

### 10.3 environment.yml（完整锁定文件）

```yaml
# 生成快照：conda env export --no-builds > environment.yml
# 复现环境：conda env create -f environment.yml

name: sandbelt
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  # 数据库与缓存
  - postgresql=16
  - timescaledb
  - postgis
  - redis-server
  # 地理空间底层
  - gdal>=3.8
  - rasterio>=1.3
  - geopandas>=0.14
  - shapely>=2.0
  - fiona>=1.9
  - pyproj>=3.6
  - netcdf4>=1.6
  - hdf5
  # ML
  - pytorch>=2.2
  - cpuonly
  # 前端运行时
  - nodejs=20
  - pip
  - pip:
    # Web 框架
    - fastapi>=0.110.0
    - uvicorn[standard]>=0.29.0
    - sqlalchemy>=2.0.0
    - psycopg2-binary>=2.9.9
    - asyncpg>=0.29.0
    - geoalchemy2>=0.15.0
    - redis>=5.0.0
    - pydantic>=2.6.0
    - pydantic-settings>=2.0.0
    # 数据采集
    - earthengine-api>=0.1.4
    - cdsapi>=0.7.0
    - xarray>=2024.1.0
    - numpy>=1.26.0
    - pandas>=2.2.0
    - scipy>=1.13.0
    # 生态分析与预测
    - scikit-learn>=1.4.0
    - prophet>=1.1.5
    # RAG & LLM
    - langchain>=0.2.0
    - langchain-anthropic>=0.1.0
    - langchain-openai>=0.1.0
    - langchain-community>=0.2.0
    - chromadb>=0.5.0
    - pypdf>=4.0.0
    - anthropic>=0.26.0
    - openai>=1.25.0
    # 调度
    - prefect>=2.19.0
```

---

### 10.4 常用 conda 环境管理命令

```bash
conda activate sandbelt              # 进入开发环境
conda deactivate                     # 退出环境
conda env list                       # 查看所有环境

conda env export --no-builds > environment.yml  # 导出快照
conda env create -f environment.yml             # 从快照复现
conda env update -f environment.yml --prune     # 更新环境

conda env remove -n sandbelt         # 删除环境（慎用）
conda clean --all -y                 # 清理下载缓存
```

---

### 10.5 requirements.txt（pip 部分，供 `pip install -r` 使用）

```
# Web 框架
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.9
asyncpg>=0.29.0
geoalchemy2>=0.15.0
redis>=5.0.0
pydantic>=2.6.0
pydantic-settings>=2.0.0

# 数据采集
earthengine-api>=0.1.4
cdsapi>=0.7.0
xarray>=2024.1.0

# 生态分析
numpy>=1.26.0
pandas>=2.2.0
scipy>=1.13.0
scikit-learn>=1.4.0
prophet>=1.1.5

# RAG
langchain>=0.2.0
langchain-anthropic>=0.1.0
langchain-openai>=0.1.0
langchain-community>=0.2.0
chromadb>=0.5.0
pypdf>=4.0.0

# LLM
anthropic>=0.26.0
openai>=1.25.0

# 调度
prefect>=2.19.0
```

---

## 11. API 接口规范

### GET /api/v1/ecological/timeseries

获取指定区域生态指标时序数据

**参数：**
```
region_id: int          # 区域 ID
indicator: str          # ndvi | evi | fvc | lst | soil_moisture
start_date: str         # YYYY-MM-DD
end_date: str           # YYYY-MM-DD
```

**响应：**
```json
{
  "region": {"id": 1, "name": "科尔沁沙地"},
  "indicator": "ndvi",
  "data": [
    {"time": "2024-01-01", "value": 0.182, "source": "MODIS"},
    {"time": "2024-01-17", "value": 0.195, "source": "MODIS"}
  ]
}
```

### GET /api/v1/ecological/current-status

获取指定区域最新生态综合状态

**响应：**
```json
{
  "region_id": 1,
  "as_of": "2024-11-15",
  "ndvi_mean": 0.214,
  "fvc": 0.28,
  "soil_moisture": 0.072,
  "risk_level": 2,
  "risk_score": 0.41,
  "wind_erosion_modulus": 128.5,
  "sand_fixation_amount": 312.0,
  "carbon_density_gc_m2": 87.3,
  "alerts": []
}
```

### GET /api/v1/prediction/ndvi-forecast

**参数：** `region_id`, `periods`（默认6，即96天）

**响应：**
```json
{
  "region_id": 1,
  "forecast": [
    {"date": "2025-01-01", "yhat": 0.18, "yhat_lower": 0.14, "yhat_upper": 0.22}
  ],
  "model": "prophet"
}
```

### POST /api/v1/prediction/scenario

情景分析接口

**请求体：**
```json
{
  "region_id": 1,
  "additional_density": 500,
  "species": "poplar",
  "years": 5
}
```

### POST /api/v1/chat/stream

SSE 流式问答（见第 7.3 节）

---

## 12. 数据源清单

| 数据类型 | 数据集 | 分辨率 | 更新频率 | 访问方式 | 备注 |
|---------|--------|--------|---------|---------|------|
| 植被指数 NDVI/EVI | MODIS MOD13A1 | 500m | 16天 | GEE | 免费，2000至今 |
| 植被指数 NDVI | Sentinel-2 SR | 10m | 5天 | GEE | 免费，2017至今 |
| 地表温度 | MODIS MOD11A2 | 1km | 8天 | GEE | 免费 |
| 土地覆被 | MCD12Q1 | 500m | 年 | GEE | 免费 |
| 土壤水分 | SMAP SPL4SMGP | 11km | 日 | GEE | 免费 |
| 降水 | ERA5 / CHIRPS | 0.25°/5km | 日/旬 | CDS API / GEE | 免费 |
| 风速风向 | ERA5 | 0.25° | 小时 | CDS API | 免费 |
| 气温/蒸散 | ERA5 | 0.25° | 小时 | CDS API | 免费 |
| DEM 高程 | SRTM 30m | 30m | 静态 | GEE | 免费 |
| 工程区边界 | 三北防护林边界数据集 | 矢量 | 静态 | NESDC | 需注册 |
| 人工林分布 | 中国人工林空间分布 | 30m | 年 | NESDC | 需注册 |
| 碳储量参考 | 中国森林地上生物量 | 30m | 2019 | NESDC | 需注册 |
| 沙化土地分布 | 中国荒漠化公报数据 | 矢量 | 5年 | 国家林草局 | 需申请 |

---

## 13. 核心算法说明

### 13.1 植被覆盖度（FVC）

采用像元二分模型：

```
FVC = (NDVI - NDVI_soil) / (NDVI_veg - NDVI_veg)
```

三北区域参数标定：
- 干旱荒漠区：NDVI_soil = 0.02，NDVI_veg = 0.80
- 半干旱草原区：NDVI_soil = 0.05，NDVI_veg = 0.85
- 半湿润区：NDVI_soil = 0.08，NDVI_veg = 0.90

### 13.2 风蚀模数（RWEQ）

基于修正风蚀方程（RWEQ），核心因子：
- **WF**（气候因子）= f(风速, 气温, 土壤水分)
- **EF**（土壤可蚀性因子）= f(土壤质地, 有机质, 碳酸钙)
- **SCF**（土壤结皮因子）= f(黏粒, 有机质)
- **K**（土壤糙度因子）= f(地表糙度)
- **COG**（植被覆盖因子）= e^(-C × FVC)

### 13.3 防风固沙服务

```
Sand_Fixation = Erosion_potential - Erosion_actual
```

Erosion_potential：FVC=0 时的理论最大风蚀量
Erosion_actual：当前植被覆盖下的实际风蚀量

### 13.4 情景分析模型

基于水量平衡方程：

```
ΔSoilMoisture = Precipitation - Evapotranspiration_natural - Transpiration_afforestation
```

当 ΔSoilMoisture 持续为负且土壤水分 < 田间持水量的 40% 时，触发"超载预警"

---

## 14. 注意事项与风险

### 14.1 数据访问

- **GEE 注册**：需申请研究用途账号，审核通常需要 1~3 个工作日。准备注册时说明是"三北防护林生态监测研究"。
- **ERA5 访问**：在 climate.copernicus.eu 注册后可免费下载，但带宽有限，建议通过 GEE 访问 ERA5-Land 产品（更快）。
- **NESDC 数据**：需注册并签订数据共享协议，下载后明确标注来源。
- **GEE 免费配额限制**：单次请求数据量有上限（maxPixels），大区域需分块或降分辨率处理。

### 14.2 模型精度

- RWEQ 模型参数需根据三北具体区域进行本地化标定，初期可参考文献中的标定值
- LSTM 预测需至少 3 年以上时序数据才能体现季节规律，冷启动阶段用 Prophet
- RAG 问答质量高度依赖语料库质量，初期应人工审核输出结果

### 14.3 工程化注意事项

- GEE Python API 调用有速率限制，Prefect 调度建议加指数退避重试
- TimescaleDB 数据量较大时（>1亿行），需配置数据保留策略（`add_retention_policy`）
- ChromaDB 生产环境建议迁移到 Qdrant（更好的持久化和并发支持）
- SSE 接口在 Nginx 反向代理时需关闭缓冲：`proxy_buffering off`

### 14.4 开发优先级原则

> **先跑通数据链路，再完善算法，最后打磨界面。**

如果 GEE 注册遇阻，Phase 1 可临时使用 NESDC 的静态历史数据集（无需实时 API）先跑通整个系统流程，等 GEE 账号批准后再替换为实时数据源。

---

*本计划书版本：v1.1 | 生成日期：2026年4月*
*系统代号：SandbeltOS — Smart Ecological Decision Support System for the Three-North Shelterbelt Program*
*开发环境：Miniforge · conda env `sandbelt` · Python 3.11 · Node.js 20（均通过 conda-forge 管理）*

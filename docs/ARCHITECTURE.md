# SandbeltOS — 架构设计与技术参考

> 本文档包含系统架构、数据库 Schema、核心算法、代码模板等技术细节。
> 可执行开发计划见 [`../PLAN.md`](../PLAN.md)。

---

## 目录

1. [系统架构总览](#1-系统架构总览)
2. [技术栈选型](#2-技术栈选型)
3. [目录结构](#3-目录结构)
4. [数据库 Schema](#4-数据库-schema)
5. [数据采集服务](#5-数据采集服务)
6. [后端服务设计](#6-后端服务设计)
7. [生态指标计算](#7-生态指标计算)
8. [预测服务](#8-预测服务)
9. [RAG 知识库设计](#9-rag-知识库设计)
10. [前端设计](#10-前端设计)
11. [API 接口规范](#11-api-接口规范)
12. [数据源清单](#12-数据源清单)
13. [核心算法说明](#13-核心算法说明)

---

## 1. 系统架构总览

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

## 2. 技术栈选型

### 2.1 后端

| 组件 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| Web 框架 | FastAPI | >=0.110 | REST API + SSE 流式输出 |
| ORM | SQLAlchemy | >=2.0 | 数据库操作 |
| 时序数据库 | TimescaleDB (PostgreSQL) | >=2.14 | 生态指标时序存储 |
| 空间扩展 | PostGIS | >=3.4 | 矢量空间查询 |
| 向量数据库 | ChromaDB | >=0.5 | RAG 文献检索 |
| RAG 框架 | LangChain | >=0.2 | 问答链编排 |
| LLM API | Anthropic Claude | claude-sonnet-4-6 | 问答生成 |
| Embedding | text-embedding-3-small (OpenAI) 或 bge-m3 (本地) | — | 文献向量化 |
| 数据调度 | Prefect | >=2.0 | 定时拉取遥感数据 |
| 遥感数据 | earthengine-api | >=0.1.4 | GEE Python 接口 |
| 气象数据 | cdsapi | >=0.7 | ERA5 下载 |
| 地理计算 | GeoPandas + Rasterio | — | 空间数据处理 |
| 缓存 | Redis | >=7 | API 响应缓存 |

### 2.2 前端

| 组件 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| 框架 | Next.js (React) | >=14 | 全栈前端 |
| 地图引擎 | Deck.gl + MapboxGL / Maplibre | — | GIS 可视化 |
| 图表库 | ECharts | >=5 | 时序图/雷达图/热力图 |
| 状态管理 | Zustand | — | 全局状态 |
| HTTP 客户端 | SWR + fetch | — | 数据请求 + SSE |
| UI 组件 | Shadcn/ui + Tailwind CSS | — | 界面组件 |
| 类型系统 | TypeScript | — | 类型安全 |

### 2.3 ML / 分析

| 组件 | 用途 |
|------|------|
| scikit-learn | 随机森林沙化风险分类 |
| PyTorch + LSTM | 植被 NDVI 时序预测 |
| Prophet | 快速时序基线预测 |
| InVEST (natcap) | 防风固沙服务量化 |
| RWEQ 模型 (自实现) | 风蚀模数计算 |

---

## 3. 目录结构

```
sandbelt-platform/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── config.py                # 环境变量配置
│   │   ├── database.py              # DB 连接池
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── ecological.py    # 生态指标接口
│   │   │       ├── gis.py           # 空间查询接口
│   │   │       ├── prediction.py    # 预测接口
│   │   │       └── chat.py          # RAG 问答接口（SSE）
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
│   ├── sql/
│   │   └── init.sql                 # 建表 SQL
│   ├── tests/
│   │   ├── test_gee.py
│   │   ├── test_rag.py
│   │   └── test_indicators.py
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
├── docs/
│   └── ARCHITECTURE.md              # 本文件
├── .env.example
├── PLAN.md
└── README.md
```

---

## 4. 数据库 Schema

> 对应文件：`backend/sql/init.sql`

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
    wind_erosion_modulus FLOAT,  -- t/(km2*a)
    sand_fixation_amount FLOAT,  -- t/(km2*a)
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

---

## 5. 数据采集服务

### 5.1 GEE NDVI 拉取

> 对应文件：`backend/app/services/gee_service.py`
> 调度频率：每 16 天自动执行

```python
import ee
import pandas as pd


def fetch_modis_ndvi(region_geom: dict, start_date: str, end_date: str) -> pd.DataFrame:
    """
    从 GEE 拉取 MODIS MOD13A1 16天合成 NDVI
    region_geom: GeoJSON geometry (三北工程区或子区域)
    返回: DataFrame(time, ndvi_mean, ndvi_min, ndvi_max, evi_mean)
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

### 5.2 ERA5 气象数据拉取

> 对应文件：`backend/app/services/era5_service.py`
> 调度频率：每日执行

```python
import cdsapi
import xarray as xr
import numpy as np
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
    返回: DataFrame with daily weather stats per grid point
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
    df['wind_direction'] = (180 + (180 / np.pi) *
                            np.arctan2(df['u10'], df['v10'])) % 360

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

> 对应文件：`backend/app/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import ecological, gis, prediction, chat

app = FastAPI(
    title="SandbeltOS API",
    version="1.0.0",
    description="三北防护林智慧生态决策支持系统"
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


@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## 7. 生态指标计算

> 对应文件：`backend/app/services/indicator_service.py`

```python
import numpy as np


def calculate_fvc(ndvi: float, ndvi_soil: float = 0.05, ndvi_veg: float = 0.85) -> float:
    """
    像元二分模型计算植被覆盖度 FVC (Fractional Vegetation Cover)
    ndvi_soil: 裸地 NDVI（三北干旱区取 0.02~0.05）
    ndvi_veg:  纯植被 NDVI（三北区取 0.80~0.90）
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
    返回: 风蚀模数 t/(km2*month)
    """
    vegetation_factor = np.exp(-3.0 * fvc)

    threshold = 5.5
    if wind_speed <= threshold:
        return 0.0
    wind_factor = (wind_speed - threshold) ** 3

    rain_factor = np.exp(-0.05 * rainfall)

    modulus = wind_factor * vegetation_factor * soil_crust_factor * rain_factor * 0.18
    return max(0.0, float(modulus))


def calculate_sand_fixation_service(
    actual_erosion: float,
    potential_erosion_no_vegetation: float
) -> float:
    """
    防风固沙服务量 = 潜在风蚀量（无植被） - 实际风蚀量
    单位: t/(km2*month)
    """
    return max(0.0, potential_erosion_no_vegetation - actual_erosion)


def estimate_carbon_density(ndvi: float, vegetation_type: str = 'mixed') -> float:
    """
    基于 NDVI 的地上生物量碳密度快速估算
    vegetation_type: 'shrub','tree','grass','mixed'
    返回: gC/m2
    """
    coefficients = {
        'tree':  {'a': 78.5, 'b': 2.1},
        'shrub': {'a': 42.3, 'b': 1.8},
        'grass': {'a': 25.0, 'b': 1.5},
        'mixed': {'a': 55.0, 'b': 1.9},
    }
    c = coefficients.get(vegetation_type, coefficients['mixed'])
    agb = c['a'] * (ndvi ** c['b'])  # g/m2
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
    fvc_score      = max(0, 1 - fvc / 0.3)
    erosion_score  = min(1, wind_erosion_modulus / 500)
    moisture_score = max(0, 1 - soil_moisture / 0.15)
    drought_score  = max(0, -precipitation_anomaly / 50)

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

---

## 8. 预测服务

> 对应文件：`backend/app/services/prediction_service.py`

```python
import torch
import torch.nn as nn
import numpy as np
from prophet import Prophet
import pandas as pd


class LSTMPredictor(nn.Module):
    """
    单变量/多变量 LSTM，用于 NDVI 时序预测
    输入: (batch, seq_len, input_size)
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
    periods: int = 6,           # 预测未来期数（16天步长则6步约3个月）
    freq: str = '16D'
) -> pd.DataFrame:
    """用 Prophet 快速预测 NDVI，支持季节性分解"""
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
    species: str = 'poplar',
    years: int = 5
) -> dict:
    """
    情景分析：增加人工造林密度对生态系统的影响模拟

    基于以下生态学关系：
    - 每公顷杨树年耗水量约 600~900mm
    - 三北干旱区年降水量 200~450mm
    - 当树木耗水量 > 降水补给时，土壤水分持续下降，
      导致"小老树"效应（FVC 下降、生长停滞）
    """
    SPECIES_WATER_USE = {
        'poplar':  750,       # 杨树 mm/year
        'willow':  700,
        'pine':    450,
        'elm':     380,
        'seabuckthorn': 300,
        'caragana':     200,  # 柠条，耐旱灌木
    }

    water_use_per_tree = SPECIES_WATER_USE.get(species, 500) / 10000
    total_water_demand_increase = additional_density * water_use_per_tree

    results = []
    sm = current_soil_moisture
    fvc = current_fvc

    for year in range(1, years + 1):
        water_deficit = total_water_demand_increase - (precipitation_mean * 0.3)
        if water_deficit > 0:
            sm = max(0.02, sm - water_deficit * 0.001)
            stress_factor = max(0, (sm - 0.04) / (0.15 - 0.04))
            fvc = max(0.02, fvc * (0.95 + 0.05 * stress_factor))
        else:
            fvc = min(0.95, fvc * 1.02)

        from app.services.indicator_service import (
            assess_desertification_risk,
            calculate_wind_erosion_modulus,
        )

        risk = assess_desertification_risk(
            fvc=fvc,
            wind_erosion_modulus=calculate_wind_erosion_modulus(
                wind_speed=6.0, fvc=fvc, rainfall=precipitation_mean / 12
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
            'warning': ('soil moisture critically low, '
                        'consider reducing density or switching to drought-tolerant species')
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
    risk_labels = ['low', 'moderate', 'high', 'extreme']
    if final['risk_level'] >= 3:
        return (
            f"HIGH RISK: Planting {species} at this density with {precip:.0f}mm/yr precipitation "
            f"leads to {risk_labels[final['risk_level']-1]} desertification risk after 5 years. "
            f"Recommendation: reduce density to <=300 trees/ha or switch to drought-tolerant shrubs "
            f"(caragana, seabuckthorn)."
        )
    elif final['risk_level'] == 2:
        return "MODERATE RISK: Monitor soil moisture closely, control planting density."
    else:
        return "LOW RISK: Current plan is viable. Continue monitoring NDVI and soil moisture."
```

---

## 9. RAG 知识库设计

### 9.1 文献入库

> 对应文件：`backend/rag/ingest.py`

```python
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
import os

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
CHROMA_PATH = "./chroma_db"


def build_knowledge_base(docs_dir: str = "./rag/docs"):
    """一次性构建向量知识库，支持 PDF 和 TXT"""
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

    print(f"Split into {len(chunks)} chunks, vectorizing...")

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_PATH,
        collection_name="sandbelt_knowledge"
    )
    vectorstore.persist()
    print(f"Knowledge base built at {CHROMA_PATH}")
    return vectorstore


def load_knowledge_base():
    return Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings,
        collection_name="sandbelt_knowledge"
    )
```

### 9.2 Prompt 模板

> 对应文件：`backend/rag/prompt_templates.py`

```python
from langchain.prompts import PromptTemplate

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

### 9.3 问答 API（SSE 流式输出）

> 对应文件：`backend/app/api/v1/chat.py`

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import anthropic
import json

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    region_id: int = 1
    include_forecast: bool = True


async def event_stream(question: str, region_id: int):
    """SSE 流式生成 RAG 回答"""
    # 1. 拉取实时生态数据
    eco_data = await get_region_latest_indicators(region_id)
    eco_context = format_eco_data_for_prompt(eco_data)

    # 2. RAG 检索
    rag = RagService()
    retrieved_docs = rag.retrieve(question, k=5)
    doc_context = "\n\n---\n\n".join([
        f"[source: {d.metadata.get('source','unknown')}]\n{d.page_content}"
        for d in retrieved_docs
    ])

    # 3. 调用 Claude API（流式）
    client = anthropic.Anthropic()

    full_prompt = ECO_DECISION_PROMPT.format(
        eco_data=eco_context,
        context=doc_context,
        question=question
    )

    # 先发送引用来源
    sources = [{'source': d.metadata.get('source', ''),
                'page': d.metadata.get('page', '')}
               for d in retrieved_docs]
    yield f"data: {json.dumps({'type': 'sources', 'data': sources}, ensure_ascii=False)}\n\n"

    # 流式发送回答
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": full_prompt}]
    ) as stream:
        for text in stream.text_stream:
            yield f"data: {json.dumps({'type': 'token', 'data': text}, ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    return StreamingResponse(
        event_stream(req.question, req.region_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


def format_eco_data_for_prompt(eco_data: dict) -> str:
    risk_labels = ['low', 'moderate', 'high', 'extreme']
    return f"""
Region: {eco_data.get('region_name', 'unknown')}
Observation time: {eco_data.get('latest_time', 'unknown')}
NDVI: {eco_data.get('ndvi_mean', 'N/A'):.3f} ({interpret_ndvi(eco_data.get('ndvi_mean'))})
FVC: {eco_data.get('fvc', 'N/A'):.1%}
Soil moisture: {eco_data.get('soil_moisture', 'N/A'):.3f} m3/m3
Monthly precipitation: {eco_data.get('precipitation_monthly', 'N/A'):.1f} mm
Desertification risk: {risk_labels[eco_data.get('risk_level', 1) - 1]}
Wind erosion modulus: {eco_data.get('wind_erosion_modulus', 'N/A'):.1f} t/(km2/month)
NDVI trend (3 months): {eco_data.get('ndvi_trend', 'stable')}
"""


def interpret_ndvi(ndvi: float) -> str:
    if ndvi is None: return "no data"
    if ndvi < 0.1:   return "bare/very sparse"
    if ndvi < 0.2:   return "sparse"
    if ndvi < 0.3:   return "low cover"
    if ndvi < 0.5:   return "moderate"
    if ndvi < 0.7:   return "good"
    return "dense"
```

---

## 10. 前端设计

### 10.1 页面结构

**主页（/）— 生态监控大屏**
- 左侧：三北工程区 GIS 地图（Deck.gl）
  - 底图：Maplibre（开源，无需 token）或 Mapbox
  - 可切换图层：NDVI 热力图 / 沙化风险图 / 风场流线图 / 降水分布图
  - 点击区域弹出 Popup 显示最新指标
- 右侧上：关键指标卡（NDVI 均值、FVC、高风险区面积、碳汇量）
- 右侧下：NDVI 时序折线图（含预测曲线）+ 风险趋势图
- 顶部：预警通知栏

**问答页（/chat）— 智慧决策助手**
- 左侧：问题历史列表
- 右侧：对话区（流式打字效果 + 引用来源展示）
- 底部：输入框 + 区域选择下拉 + 预设快捷问题

### 10.2 关键前端代码模板

#### SSE 流式接收

> 对应文件：`frontend/lib/sse.ts`

```typescript
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

#### NDVI 热力图层

> 对应文件：`frontend/components/map/NDVILayer.tsx`

```typescript
import { HeatmapLayer } from '@deck.gl/aggregation-layers';

export function createNDVILayer(data: any[]) {
  return new HeatmapLayer({
    id: 'ndvi-heatmap',
    data,
    getPosition: (d: any) => [d.longitude, d.latitude],
    getWeight: (d: any) => d.ndvi_mean,
    radiusPixels: 30,
    colorRange: [
      [255, 255, 204],   // very low NDVI
      [161, 218, 180],
      [65, 182, 196],
      [44, 127, 184],
      [37, 52, 148],     // high NDVI
    ],
    intensity: 1,
    threshold: 0.05,
  });
}
```

---

## 11. API 接口规范

### GET /api/v1/ecological/timeseries

获取指定区域生态指标时序数据。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| region_id | int | 区域 ID |
| indicator | str | ndvi / evi / fvc / lst / soil_moisture |
| start_date | str | YYYY-MM-DD |
| end_date | str | YYYY-MM-DD |

**响应：**
```json
{
  "region": {"id": 1, "name": "Horqin Sandy Land"},
  "indicator": "ndvi",
  "data": [
    {"time": "2024-01-01", "value": 0.182, "source": "MODIS"},
    {"time": "2024-01-17", "value": 0.195, "source": "MODIS"}
  ]
}
```

### GET /api/v1/ecological/current-status

获取指定区域最新生态综合状态。

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

**参数：** `region_id`, `periods`（默认 6，即 96 天）

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

SSE 流式问答（见第 9.3 节）。

---

## 12. 数据源清单

| 数据类型 | 数据集 | 分辨率 | 更新频率 | 访问方式 | 备注 |
|---------|--------|--------|---------|---------|------|
| 植被指数 NDVI/EVI | MODIS MOD13A1 | 500m | 16天 | GEE | 免费，2000至今 |
| 植被指数 NDVI | Sentinel-2 SR | 10m | 5天 | GEE | 免费，2017至今 |
| 地表温度 | MODIS MOD11A2 | 1km | 8天 | GEE | 免费 |
| 土地覆被 | MCD12Q1 | 500m | 年 | GEE | 免费 |
| 土壤水分 | SMAP SPL4SMGP | 11km | 日 | GEE | 免费 |
| 降水 | ERA5 / CHIRPS | 0.25deg/5km | 日/旬 | CDS API / GEE | 免费 |
| 风速风向 | ERA5 | 0.25deg | 小时 | CDS API | 免费 |
| 气温/蒸散 | ERA5 | 0.25deg | 小时 | CDS API | 免费 |
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
FVC = (NDVI - NDVI_soil) / (NDVI_veg - NDVI_soil)
```

三北区域参数标定：

| 区域类型 | NDVI_soil | NDVI_veg |
|---------|-----------|----------|
| 干旱荒漠区 | 0.02 | 0.80 |
| 半干旱草原区 | 0.05 | 0.85 |
| 半湿润区 | 0.08 | 0.90 |

### 13.2 风蚀模数（RWEQ）

基于修正风蚀方程，核心因子：
- **WF**（气候因子）= f(风速, 气温, 土壤水分)
- **EF**（土壤可蚀性因子）= f(土壤质地, 有机质, 碳酸钙)
- **SCF**（土壤结皮因子）= f(黏粒, 有机质)
- **K**（土壤糙度因子）= f(地表糙度)
- **COG**（植被覆盖因子）= e^(-C * FVC)

### 13.3 防风固沙服务

```
Sand_Fixation = Erosion_potential - Erosion_actual
```

- Erosion_potential：FVC=0 时的理论最大风蚀量
- Erosion_actual：当前植被覆盖下的实际风蚀量

### 13.4 情景分析模型

基于水量平衡方程：

```
delta_SoilMoisture = Precipitation - ET_natural - Transpiration_afforestation
```

当 delta_SoilMoisture 持续为负且土壤水分 < 田间持水量的 40% 时，触发超载预警。

---

*本文档版本：v2.0 | 更新日期：2026-04-16*
*从 PLAN.md v1.1 拆分而来，保留所有技术设计内容*

# Phase 5 — 预测与情景分析 执行计划

> 创建日期：2026-05-12
> 对应 PLAN.md §Phase 5（NDVI 预测 + 造林情景模拟）
> 上游依赖：Phase 1 数据 + Phase 3 指标引擎（均已落地）

---

## 0. 目标与边界

**做什么（必交付）：**
- NDVI 时序预测（Prophet 基线，未来 96 天 = 6 个 16 日步长）
- 造林情景分析（指定树种 × 密度 × 年限 → 多年生态指标演化）
- 前端预测曲线（历史实线 + 预测虚线 + 置信带）+ 情景交互面板

**不做（明确排除）：**
- LSTM 训练（原 PLAN §5.7 标注为可选；当前合成数据上没意义）
- 多指标联合预测（仅 NDVI；FVC 由 NDVI 推导，不单独建模）
- 后端持久化预测结果到 PG（先内存/Redis 缓存，必要时再升级）
- 用户保存"我的方案"功能（无认证体系）

**完成定义（Done = 三个可演示动作）：**
1. 在仪表盘 NDVI 图上看到一条预测延长线（含置信区间阴影）
2. 在情景面板调"杨树 + 800 株/公顷 + 5 年"→ 图表实时刷新年度 FVC/SM/风险演化
3. `pytest backend/tests/test_prediction.py` 全绿

---

## 1. 需要你决策的事项（写代码前定）

以下 5 项每一项都标了我的**默认建议**和取舍。如果默认 OK 直接进 §2;否则告诉我换哪个。

| # | 决策点 | 选项 | 建议默认 | 影响 |
|---|--------|------|---------|------|
| D1 | **数据真实性** | (a) 用现有合成 NDVI 直接预测 (b) Phase 5 推迟到接入真实 GEE 数据后 | **(a) 合成跑通,前端打"演示数据"水印** | (b) 工程更扎实但要先解 GEE 账号 + 重跑 Phase 1,押后 2 周以上 |
| D2 | **预测水平** | (a) 6 步 × 16 天 = 96 天 (b) 24 步 ≈ 1 年 (c) 两套都给) | **(c) 默认 12 步 ≈ 半年,query 参数可调到 24** | (a) 演示弱;(b) 合成数据外推风险大;(c) 折中 |
| D3 | **缓存策略** | (a) 不缓存,每请求 fit 一次 (b) Redis 缓存(region_id, horizon) 30 分钟 (c) 新建 `ndvi_forecasts` 持久表 | **(b) Redis** | Prophet fit ~200ms 但叠多用户会卡;(c) 工作量大没必要 |
| D4 | **情景面板放哪** | (a) 仪表盘新加一个 section (b) 新增 `/scenario` 路由 (c) 进 ChatWidget 作为 tool-call | **(a) 仪表盘新 section** | (b) 路由跳走脱离地图上下文;(c) 太炫但实现成本高 |
| D5 | **风险模型在情景中的复用** | (a) 直接调 `indicators.assess_risk` (b) 单写一个 `scenario.py` 内部模型 | **(a) 直接复用** | 关键:ARCHITECTURE.md §8 里的代码用了一套老常数(`assess_desertification_risk`、`SPECIES_WATER_USE` 在那里)。**必须以 `indicators.py` 实际代码为准**,文档随后同步 |

> ⚠️ **特别提示 D1**:Phase 1 数据是合成的,Prophet 在合成数据上的预测约等于"把合成器外推一次"。建议**前端在预测线旁加 `* 基于合成数据,真实数据接入后重新校准` 角标**,避免演示时被点破。

---

## 2. 工作流 A — Prophet NDVI 预测

### 文件清单(新增/修改)

```
backend/app/services/
├── prediction.py          [新] Prophet fit + forecast,可选 Redis 缓存
└── scenario.py            [新] 见 §3

backend/app/api/v1/
└── prediction.py          [新] 2 个路由 + Pydantic schemas

backend/app/main.py        [改] include_router

backend/app/models/schemas.py  [改] 加 ForecastResponse / ScenarioRequest / ScenarioResponse

backend/tests/
├── test_prediction.py     [新] Prophet 单测 + API 集成
└── test_scenario.py       [新] 见 §3
```

### A.1 `services/prediction.py` 设计

```python
"""NDVI forecasting service.

Pure function over a timeseries — fits Prophet on historical eco_indicators
rows for one (region, indicator), forecasts horizon steps, returns
date+yhat+lower+upper rows. No DB writes.

Caching is shallow: keyed on (region_id, indicator, horizon, as_of_day),
Redis TTL 30 min. Misses fit a fresh Prophet model.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

import pandas as pd
from prophet import Prophet
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import ecological as eco_svc


@dataclass(frozen=True)
class ForecastPoint:
    date: str           # ISO YYYY-MM-DD
    yhat: float
    yhat_lower: float
    yhat_upper: float


@dataclass(frozen=True)
class ForecastResult:
    region_id: int
    indicator: str
    model: Literal["prophet"]
    fitted_on_n_points: int
    history_end: str
    horizon_steps: int
    freq: str           # "16D"
    points: list[ForecastPoint]


async def forecast_indicator(
    region_id: int,
    indicator: str,
    horizon_steps: int,
    db: AsyncSession,
    freq: str = "16D",
) -> ForecastResult:
    """Forecast `indicator` for `region_id` `horizon_steps` ahead.

    Pulls the full available history via ecological service. Requires
    >= 24 historical points (otherwise Prophet seasonality is unreliable);
    raises ValueError if insufficient data.
    """
    # 1) Pull history (reuse get_timeseries) → DataFrame[ds, y]
    # 2) Fit Prophet with yearly_seasonality=True, weekly=False, daily=False,
    #    seasonality_mode='multiplicative', changepoint_prior_scale=0.05
    # 3) make_future_dataframe(periods=horizon_steps, freq=freq)
    # 4) predict, slice tail(horizon_steps)
    # 5) Clamp yhat/lower/upper to [0, 1] (NDVI bounds)
    # 6) Return ForecastResult
    ...
```

**参数标定理由:**
- `yearly_seasonality=True`:NDVI 有强年度周期(植被生长季)
- `seasonality_mode='multiplicative'`:植被覆盖度高时季节波动幅度更大,符合实际
- `changepoint_prior_scale=0.05`:三北区年际变化不剧烈,保守值避免过拟合短期噪声
- `clamp [0,1]`:Prophet 不知道 NDVI 物理边界,必须手动裁剪

**缓存层(D3 决策为 b 时):**

```python
# app/services/cache.py [新] 极轻 Redis 包装,只暴露 get_json/set_json
# 缓存 key:f"forecast:{region_id}:{indicator}:{horizon}:{date.today()}"
```

如果 D3 选 (a),整段缓存代码跳过,`prediction.py` 不引用 cache。

### A.2 API 路由

```python
# backend/app/api/v1/prediction.py
@router.get("/ndvi-forecast")
async def get_ndvi_forecast(
    region_id: int = Query(1),
    horizon: int = Query(12, ge=1, le=24, description="16-day steps ahead"),
    db: AsyncSession = Depends(get_db),
) -> ForecastResponse:
    """NDVI 未来 N 期(每期 16 天)Prophet 预测。"""
    result = await pred_svc.forecast_indicator(region_id, "ndvi", horizon, db)
    return ForecastResponse.from_dataclass(result)
```

**响应 schema:**
```json
{
  "region_id": 1,
  "indicator": "ndvi",
  "model": "prophet",
  "fitted_on_n_points": 115,
  "history_end": "2024-12-19",
  "horizon_steps": 12,
  "freq": "16D",
  "points": [
    {"date": "2025-01-04", "yhat": 0.18, "yhat_lower": 0.14, "yhat_upper": 0.22},
    ...
  ]
}
```

### A.3 测试(`test_prediction.py`)

| 测试 | 类型 | 验收 |
|------|------|------|
| `test_forecast_returns_horizon_points` | unit | 给 100 点假数据,horizon=6,返回 6 点 |
| `test_forecast_clamps_ndvi_bounds` | unit | 所有 yhat/lower/upper ∈ [0,1] |
| `test_forecast_insufficient_history_raises` | unit | n<24 时抛 ValueError |
| `test_forecast_api_smoke` | integration | `GET /api/v1/prediction/ndvi-forecast?region_id=1` 返回 200,结构合法 |
| `test_forecast_redis_cache_hit` | integration (D3=b) | 同一参数二次请求 < 50ms |

---

## 3. 工作流 B — 造林情景分析

### B.1 设计原则

**完全纯函数,不读 DB**(输入参数 + 当前指标快照 → 多年演化输出)。情景模型核心是"水量平衡 + FVC 衰减反馈",和 `indicators.assess_risk` 解耦。

每一年迭代做三件事:
1. 计算水分赤字 `water_deficit = species_water_use(树种, 密度) - 有效降水`
2. 更新土壤水分 `SM_{t+1} = max(SM_floor, SM_t - water_deficit · k)`
3. 用新 SM 反推 FVC 衰减,再调 `indicators.assess_risk` 出风险等级

### B.2 `services/scenario.py`

```python
"""Afforestation scenario simulation.

Closed-form multi-year projection: given current FVC / soil moisture /
precipitation and a planting plan (species, density, years), iterate
yearly to project FVC, SM, and desertification risk.

Reuses indicators.assess_risk for risk scoring — single source of truth
for risk math.
"""
from dataclasses import dataclass
from typing import Literal

from app.services.indicators import (
    assess_risk,
    calculate_fvc,
    calculate_wind_erosion,
)

Species = Literal["poplar", "willow", "pine", "elm", "seabuckthorn", "caragana"]

# Annual water demand per tree (m³/tree/year) — derived from species water
# use coefficients in mm/yr times canopy footprint, see _ANNUAL_WATER_USE_MM
# in ARCHITECTURE.md §8. Recalibrated to match indicators.py's FVC bounds.
SPECIES_WATER_USE_MM: dict[Species, float] = {
    "poplar": 750,
    "willow": 700,
    "pine": 450,
    "elm": 380,
    "seabuckthorn": 300,
    "caragana": 200,
}

SM_FLOOR = 0.02            # m³/m³ — physical minimum
SM_STRESS_THRESHOLD = 0.04 # below this FVC starts collapsing
FVC_GROWTH_RATE = 0.02     # surplus year FVC gain
FVC_STRESS_COEF = 0.05     # stress year FVC decay


@dataclass(frozen=True)
class ScenarioInput:
    region_id: int
    current_fvc: float
    current_soil_moisture: float
    annual_precip_mm: float
    avg_wind_speed_ms: float
    species: Species
    additional_density_per_ha: int  # 株/公顷
    years: int                       # 1..20


@dataclass(frozen=True)
class YearlyProjection:
    year: int
    fvc: float
    soil_moisture: float
    water_deficit_mm: float
    wind_erosion: float
    risk_level: int
    risk_score: float
    warning: str | None


@dataclass(frozen=True)
class ScenarioResult:
    input: ScenarioInput
    yearly: list[YearlyProjection]
    recommendation: str


def simulate(input: ScenarioInput) -> ScenarioResult:
    """Project FVC / SM / risk over `input.years` under planting plan."""
    ...


def _generate_recommendation(yearly: list[YearlyProjection], input: ScenarioInput) -> str:
    """Heuristic advice based on final-year risk + worst-year SM."""
    ...
```

**算法骨架(伪代码):**

```
sm = input.current_soil_moisture
fvc = input.current_fvc
for y in 1..years:
    water_demand_mm = SPECIES_WATER_USE_MM[species] * density_factor(additional_density)
    effective_precip = input.annual_precip_mm * 0.3   # 30% 有效供给(蒸散损失后)
    deficit = max(0, water_demand_mm - effective_precip)

    if deficit > 0:
        sm = max(SM_FLOOR, sm - deficit * 0.001)
        stress = max(0, (sm - SM_STRESS_THRESHOLD) / (0.15 - SM_STRESS_THRESHOLD))
        fvc = max(0.02, fvc * (1 - FVC_STRESS_COEF * (1 - stress)))
    else:
        fvc = min(0.95, fvc * (1 + FVC_GROWTH_RATE))

    wem = calculate_wind_erosion(input.avg_wind_speed_ms, fvc, sm)
    risk = assess_risk(fvc, wem, sm, lst_c=None)

    yearly.append(YearlyProjection(year=y, fvc=fvc, soil_moisture=sm,
                                    water_deficit_mm=deficit,
                                    wind_erosion=wem,
                                    risk_level=risk.risk_level,
                                    risk_score=risk.risk_score,
                                    warning=_warning(sm, fvc)))
```

### B.3 API 路由

```python
@router.post("/scenario")
async def post_scenario(req: ScenarioRequest, db: AsyncSession = Depends(get_db)):
    """造林情景分析:树种×密度×年限 → 多年生态指标演化。"""
    # 1) 从 ecological_svc 读 region 当前快照(FVC、SM、年均降水、风速)
    # 2) 调 scenario.simulate
    # 3) 返回 ScenarioResponse
    ...
```

**请求体:**
```json
{
  "region_id": 1,
  "species": "poplar",
  "additional_density_per_ha": 500,
  "years": 5
}
```

### B.4 测试(`test_scenario.py`)

| 测试 | 类型 | 验收 |
|------|------|------|
| `test_simulate_returns_years_rows` | unit | years=5 返回 5 个 YearlyProjection |
| `test_drought_species_caragana_stable` | unit | 柠条 + 500 株/ha + 250mm 降水,5 年后 risk_level <= 2 |
| `test_poplar_overdensity_warns` | unit | 杨树 + 1500 株/ha + 250mm 降水,出现 "small old tree" warning |
| `test_scenario_api_smoke` | integration | POST 返回 200,yearly 数组长度匹配 years |
| `test_recommendation_text_chinese` | unit | recommendation 含中文,长度 > 20 |

---

## 4. 工作流 C — 前端

### C.1 文件清单

```
frontend/src/lib/
└── api.ts                       [改] 加 fetchForecast / postScenario + 类型

frontend/src/components/
├── NdviChart.tsx                [改] 接受可选 forecast prop,叠加预测段
├── ScenarioPanel.tsx            [新] 控件 + 结果图,自包含 useState
├── ScenarioControls.tsx         [新] 树种 select + 密度 slider + 年限 slider
├── ScenarioChart.tsx            [新] 多线图:FVC / SM / risk_score 共轴
└── DemoDataBadge.tsx            [新] 角标"演示数据" (D1=a 时)

frontend/src/app/dashboard/
└── page.tsx                     [改] 加 <ScenarioPanel> section
```

### C.2 NDVI 图叠加预测

`NdviChart` 现已存在,扩展方式:

```tsx
interface NdviChartProps {
  ndviData: TimeseriesRecord[];
  eviData: TimeseriesRecord[];
  forecast?: ForecastPoint[];      // [新] 可选预测点
}
```

预测 series 配置:
- 主线 `yhat`: `lineStyle: { type: 'dashed', color: '#16a34a' }`,接在历史尾点之后
- 置信带:用 ECharts `series.areaStyle` + 两条隐形上/下界堆叠,半透明色
- Tooltip 区分"实测/预测"

### C.3 情景面板交互

**布局(仪表盘 NDVI 卡片下方新增一行 grid):**

```
┌──────────────────────────────────────────────────────┐
│ 造林情景分析                                          │
├─────────────┬────────────────────────────────────────┤
│ 树种 [下拉]  │  FVC / SM / 风险 多年趋势图              │
│ 密度 [滑块]  │  (3 条线 + 风险等级背景色带)            │
│ 年限 [滑块]  │                                        │
│ [模拟]      │  推荐:杨树 500/ha,5 年后中等风险...     │
└─────────────┴────────────────────────────────────────┘
```

**交互:**
- 控件 onChange 防抖 400ms → POST `/api/v1/prediction/scenario`
- 加载态:控件区灰边框,图表骨架屏
- 错误态:Toast(可选)+ 图表保留上一次结果

### C.4 (D1=a 时)演示数据角标

`<DemoDataBadge>` 浮在预测线右上角和情景图右上角,文本"演示数据 · 真实数据接入后重新校准",hover 显示更长说明。

---

## 5. 排期(按个人开发者节奏,工作日数)

| 日 | 工作 | 产出 |
|----|------|------|
| D1 | §2 决策定稿(花 30 分钟) + 后端 `prediction.py` + 单测 | Prophet 出 forecast,test 通过 |
| D2 | 后端 `scenario.py` + 单测 | `simulate()` 单测全过,常数表稳定 |
| D3 | 后端 API 路由 + Pydantic schemas + 集成测试 + 注册到 main.py | curl 双端点都拿到合法 JSON |
| D4 | 前端 `api.ts` 类型 + `NdviChart` 叠加预测线 | 仪表盘 NDVI 图能看到预测段 |
| D5 | 前端 `ScenarioPanel` 三件套(Controls + Chart + Panel) | 调参 → 图刷新 |
| D6 | 联调 + DemoDataBadge + 边界情况打磨(空数据、network 错) + e2e 手测 | 演示就绪 |

**合计 ~6 工作日**(全职);非全职 × 1.5~2 = 10-12 天。

> 与原 PLAN.md "Phase 5 ≈ 2 周"基本对齐,因为 LSTM 砍了所以略快。

---

## 6. 风险清单与回退

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Prophet 在合成数据上预测发散 | 中 | 预测线明显不合理 → 演示效果差 | 加 `[0,1]` 硬裁剪 + 调小 `changepoint_prior_scale` 到 0.01 |
| Redis 没装/没起 | 低 | 缓存层报错 | 缓存写成可选,失败降级到无缓存(只 log warning) |
| Prophet 装包慢/编译失败(macOS arm64) | 中 | 阻塞 D1 | 已在 requirements.txt 中,如失败回退 `statsmodels.tsa.ExponentialSmoothing`(简陋但能跑) |
| 情景模型常数误差大 | 高 | 推荐文本可信度差 | 算法是 demo 级,文档明确说明"经验模型,实际决策需专业评估" |
| 前端 ECharts 双 yAxis 视觉混乱 | 中 | 用户看不懂 | 改成两张并排的小图,而不是共轴 |
| 真实数据接入后 Prophet 重新打分崩了 | 低 | Phase 6 阻塞 | 单测里加 golden 数据夹具,真实数据进来时跑回归 |

---

## 7. 验收清单(关项目时勾)

- [ ] `pytest backend/tests/test_prediction.py backend/tests/test_scenario.py` 全绿
- [ ] `curl 'localhost:8000/api/v1/prediction/ndvi-forecast?region_id=1&horizon=12'` 返回合法 JSON,horizon 段 == 12
- [ ] `curl -X POST localhost:8000/api/v1/prediction/scenario -d '{...poplar 500 5 years...}'` 返回 5 年 projection
- [ ] 仪表盘 NDVI 图右侧延伸出虚线 + 浅绿置信带
- [ ] 情景面板调"杨树 500 株 5 年"和"柠条 500 株 5 年"出现明显不同的演化轨迹
- [ ] 演示数据角标在 D1=a 时正常显示
- [ ] git 提交划分:1 commit/工作流(prediction service / scenario service / API / 前端 chart / 前端 panel / 联调收尾)

---

## 8. 与 ARCHITECTURE.md / PLAN.md 的同步

完成后需要修订的文档(单独一个 commit,不混在代码里):

1. `PLAN.md` §Phase 5:把 [ ] 改 [x] + 加完成日期
2. `docs/ARCHITECTURE.md` §8 "预测服务":把 `assess_desertification_risk` 旧函数名改成 `assess_risk`(与 indicators.py 对齐),`SPECIES_WATER_USE` 表对齐到 `scenario.py` 实际值
3. `README.md` 顶部"核心能力"加一句:"预测与情景分析 — Prophet NDVI 12 期预测 + 6 种树种造林情景模拟"

---

*本计划版本:v1 | 拟稿日期:2026-05-12 | 基于 commit 3f3c895*

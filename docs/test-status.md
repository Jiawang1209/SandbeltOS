# SandbeltOS · 端到端验证报告

> **基线日期**：2026-05-18
> **环境**：本地 macOS / conda `sandbelt` / Homebrew Postgres 16 / Brew Redis 8.6.3
> **基线 commit**：`e6a75c8` (clean-env hotfix) + 本次发现修复
> **里程碑**：路线图 1️⃣ 端到端验证 + demo 录制 — 验证部分（1.2 + 1.3 + 1.5）

---

## 一、pytest 套件结果

| 指标 | 值 |
|---|---|
| 总数 | 118 |
| 通过 | 118 ✅ |
| 失败 | 0 |
| 跳过 | 0 |
| 耗时 | ~48 s |

**第一次跑发现的 5 个失败 → 已全部修复**：

| # | 测试 | 根因 | 修复 |
|---|---|---|---|
| 1 | `test_prediction::TestForecastSeries::test_returns_horizon_points` | `prophet` 未在 `sandbelt` env 安装 | `pip install prophet redis` |
| 2 | `test_prediction::test_clamps_to_ndvi_bounds` | 同上 | 同上 |
| 3 | `test_prediction::test_dates_are_iso_strings` | 同上 | 同上 |
| 4 | `test_prediction::test_forecast_api_smoke` | Prophet 1.3+ 不接受 timezone-aware `ds` 列（PG `TIMESTAMPTZ` 默认带 `+08`） | `app/services/prediction.py`：`pd.to_datetime(df["ds"], utc=True).dt.tz_localize(None)` |
| 5 | `test_timeseries_api::test_regions_endpoint` | 测试期望 `data["regions"]`，API 实际返回 GeoJSON `FeatureCollection`（前端权威 contract） | `tests/test_timeseries_api.py`：改测 `features` 和 `properties.name` |

**附带**：`pytest.ini` 注册了 `unit` / `integration` 两个自定义 mark（清掉 20 个 `PytestUnknownMarkWarning`）。

---

## 二、5 个核心动作手测结果

后端 API 烟测全过（curl + Chrome DevTools），浏览器 UI 验证如下。

| # | 动作 | 后端 | 前端 | 备注 |
|---|---|---|---|---|
| 1 | 双沙地视图（地图 + 风险卡 + NDVI 趋势） | ✅ | ✅ | console 0 报错；地图渲染科尔沁 + 浑善达克 + 年趋势对比柱 |
| 2 | 单沙地视图（点击科尔沁 → NDVI + 预测虚线 + 角标） | ✅ | ✅ | forecast 在 `selectedId` 变化时正确触发（`reqid=105 /ndvi-forecast?region_id=1&horizon=12 [200]`），Prophet fit on 115 NDVI 点；预测值约 0.03–0.05（合成数据冬季外推），虚线被画在图底容易视觉错过，**功能正确** |
| 3 | 情景面板（树种 × 密度 × 年限） | ✅ | ✅ | 默认 `柠条 600/ha 5y` 自动跑出"高风险"+ 中文建议（"将密度降至 ≤ 300 株/公顷，或改用沙棘、柠条等抗旱树种"），多年趋势图渲染正常；6 种树种全部可选 |
| 4 | `/chat` SSE 流式问答 | RAG 检索 ✅ / LLM ❌ | UI ✅ | 见下方"已知阻塞" |
| 5 | Landsat 时空对比（swipe） | Server URL ✅ / 浏览器加载 ❌ | UI ✅ | 见下方"已知阻塞" |

### 4 & 5 的已知阻塞（环境侧，非项目代码 bug）

| 阻塞 | 现象 | 根因 | 修复路径 |
|---|---|---|---|
| ~~**LLM provider 已下线**~~ ✅ 已解决 | 原 `deepseek-v3:671b` → "Error code: 422 - 模型已下线" | 中科院 uni-api 把该模型下线了。RAG 检索 / 路由 / 实时数据注入均工作；只挂在 LLM 调用上 | 切到 `deepseek-v3.2`（同源继任者），SSE 流式 + token 输出实测通过。`.env.example` 默认值同步更新，并列出探测时仍在线的备选：`deepseek-v4-flash` / `gpt-oss-120b` / `minimax-m27` |
| **Landsat tile 浏览器侧 SSL 失败** | `https://earthengine.googleapis.com/.../tiles/...` → `net::ERR_ABORTED`；后端 `/api/v1/basemap/landsat` curl 直连返回正确 tile URL | 本机 Clash 代理（127.0.0.1:7897）SSL 拦截 `*.googleapis.com`。后端首次也 500（GEE OAuth token refresh 走代理被 SSL 中断），重启时 `unset http_proxy https_proxy` 后后端 OK，但浏览器仍走系统代理 | demo 录制前关闭 Clash 或在 Clash 规则里把 `*.googleapis.com` + `*.earthengine.com` 加 DIRECT |

> Demo 视频建议：录制前关闭代理；或录第 4、5 步时用 OBS 切到一段静态截图加旁白解释。

---

## 三、PLAN.md 完成度复核（实测 vs 文档）

| 阶段 | PLAN.md 标注 | 实测 | 漂移项 |
|---|---|---|---|
| Phase 3 · 生态评估引擎 | 🟡（3 个完成标志未勾） | 实际 2/3 已做 | **3.10 4 个指标卡** ✅（NDVI / FVC / 碳密度 / 沙化风险等级全在单沙地视图）；**3.11 风险图层切换按钮** ✅（"植被覆盖 / 沙化风险 / 像素热点" 三按钮在）；**3.12 预警通知栏** ✅（红色"极高风险预警 5 条"banner 在）；**3.13 Prefect 定时 flow** ❌（未起 Prefect 进程，没看到调度面板） |
| Phase 4 · RAG 问答 | 🟡（3 个完成标志未勾） | 实际 2/3 已做 | **4.9 引用展开** ✅（右侧栏自动列出 5 条引用 + PDF 名 + page 号 + score）；**4.10 预设快捷问题** ✅（新对话页 6 个按钮，分"风险&趋势/方法论/实务决策" 3 组）；**4.11 5 类问题人工质量评估** ❌（被 LLM 下线阻塞） |

→ **结论**：Phase 3/4 的"未完成"中大半其实早完成，只是 PLAN.md 没勾上。真正缺的只剩两项：Prefect 调度未起 + RAG 人工质量评估未跑。

---

## 四、文档漂移与数据校准（已修）

### 4.1 文档/UI 漂移

| 位置 | 现状 → 应改 | 状态 |
|---|---|---|
| `SiteFooter` | "Ver. Phase 4 · RAG-powered Copilot" → "Ver. Phase 5 · Prediction & Scenario" | ✅ 已修 |
| `app/page.tsx` 卡片 | RAG/预测分析 显示 "Phase 4" / "Phase 5"（无 ✓） → 加 ✓ + 绿色样式 | ✅ 已修 |
| `chat/MetricsPanel` | FVC `null%` / soil_moisture `0.1171%`（漏 ×100） → null 显 "—"，fraction ×100 显 "11.7%" | ✅ 已修 |
| `chat-types.ts` `Metrics` | `fvc: number` → `fvc: number \| null`（同步 ndvi/wind/soil） | ✅ 已修 |
| `README.md` 步骤 2 | 提示 conda 装 `redis-server` → macOS 改 brew，加 fallback；提示 pip install 装 prophet | ✅ 已修 |
| `README.md` 步骤 4 | 单 conda PG 路径 → 拆 A/B：conda PG 与 brew PG16 | ✅ 已修 |
| `README.md` 常见排错 | 缺 Clash 代理 / LLM 下线 / Prophet 缺失 的处置 → 加 3 行 | ✅ 已修 |

### 4.2 沙地面积数据校准（**重要发现**）

**起因**：演示中发现顶部 KPI "监测面积 24,143 km²" 与公开统计严重不符。

**真相**：

| 沙地 | 公开真实面积 | 公开经纬度范围 | A 前 DB | bbox(A 前) |
|---|---|---|---|---|
| 科尔沁 | 5.06–6.63 万 km²（百度/维基） | 41.7°–47.65°N, 116.36°–126.25°E | 2,742 km²（OSM 真实多边形） | 42–44°N, 118–123°E（**只覆盖真实范围 1/3**） |
| 浑善达克 | 2.38–3.84 万 km²（不同口径） | 锡林郭勒南端, 东西长 ~450 km | 21,400 km²（**历史 fallback 写死**） | 41.5–43.5°N, 113–117.5°E（4.5°×2° ≈ 410km 临界） |

**根因双重叠加**：
1. Bbox 太小（科尔沁尤其）—— Overpass 搜索范围圈不全
2. OSM 中国境内 `natural=sand` tag **极稀疏**（实测覆盖率 1–5%）—— 即便 bbox 扩到真实范围也只能拉到 2,734 km²（科尔沁）/ 263 km²（浑善达克）

**A 方案（扩 bbox）单独无效**：扩到 (116, 41.5, 126.5, 47.7) 后科尔沁多边形数 N→306 但总面积 2,742→2,734（持平）；浑善达克更糟（21,400 写死值 → 263 真实 OSM 覆盖）。

**B 方案首次尝试**：保留 OSM 多边形 + 仅改写 area_km2 → KPI 数字对了，但地图视觉变成稀疏小斑块散落，浑善达克"消失"。

**B 修订（已实施）**：覆盖率 < 50% 时，**几何也降级为 bbox 矩形**（不再保留稀疏 OSM 多边形），area_km2 写入权威值：
- 科尔沁 50,600 km²（bbox 119–126.5°E × 42–47.7°N，百度百科 / 《中国八大沙漠四大沙地》2024）
- 浑善达克 23,800 km²（bbox 111.5–117°E × 41–44°N，维基百科保守口径）

两矩形 bbox 之间留 **2°（≈200km）的可见空隙**，对应真实地理上大兴安岭对两片沙地的分割。修复后地图上看到两片明显的橙色填充矩形，KPI 显示 **74,400 km²**（截图 [`01_dashboard_combined.png`](demos/01_dashboard_combined.png)）。

**C 方案（路线图 2️⃣ 时一并做）**：接 NESDC 官方"中国沙化土地分布"矢量数据替换 OSM 多边形 / 粗矩形，几何 + 面积全权威。

---

## 五、本次修复 commit 范围

待提交：

```
M backend/app/services/prediction.py     # Prophet tz fix
M backend/pytest.ini                       # register unit/integration marks
M backend/tests/test_timeseries_api.py    # FeatureCollection contract
A docs/test-status.md                      # 本文件
A docs/demos/01_dashboard_combined.png    # 双沙地视图截图
A docs/demos/02_horqin_solo.png           # 科尔沁单视图截图
A docs/demos/03_compare_swipe.png         # 对比模式打开
A docs/demos/04_compare_loaded.png        # 对比模式 + 年份下拉
A docs/demos/05_landsat_swipe_loaded.png  # 对比 + Landsat 加载中
```

不提交：`prophet` / `redis` 装在 env 里（应同步进 `backend/requirements.txt` 或 README 步骤）。

---

## 六、下一里程碑（路线图 2️⃣ 真实 GEE 数据接入前的剩余项）

- [ ] 关闭/绕过 Clash 后录 2-3 分钟 demo 视频（1.4）
- [ ] `docker compose up` 在干净容器走 README 五步（1.1，原计划推后）
- [ ] 把 `prophet`、`redis` 写进 `backend/requirements.txt` 或 README pip 列表
- [ ] PLAN.md 把 Phase 3 的 3.10/3.11/3.12 和 Phase 4 的 4.9/4.10 标 ✅，剩余两项明确拆到「后续扩展」
- [ ] 选个仍在线的 LLM endpoint（uni-api 上的 qwen3:235b 已下线）
- [ ] 修 footer 版本标签 + FVC null 展示

---

## 七、里程碑 2️⃣ 真实 GEE 数据接入 · 首批落地（2026-05-18 续）

| 子项 | 状态 | 结果 |
|---|---|---|
| MODIS NDVI/EVI 真实数据替换 (2020-2024, 16-day) | ✅ | 4 组 × 115 行 `MODIS_GEE`,科尔沁 NDVI mean 0.33 / 浑善达克 0.18 |
| 真实沙地边界提取(MODIS NDVI<0.48,生长季均值) | ✅ | 科尔沁 1 矩形 → 265 多边形,浑善达克 1 → 46;`area_km2` 保持权威覆盖(50,600 / 23,800) |
| pytest 套件回归 | ✅ | 118/118 通过 (~57 s),与里程碑 1️⃣ 一致 |
| API 端到端 (`/gis/regions` + `/ecological/timeseries`) | ✅ | FeatureCollection 返回正确;timeseries `source` 字段已是 `MODIS_GEE` |
| ERA5 weather_data | 已经是真实 | 5 年 × 2 区域 × 1827 日,无需补 |

### 关键修复

| Bug | 现象 | 修复 (commit) |
|---|---|---|
| GEE `Too many concurrent aggregations` | `collection.map(reducer).getInfo()` 一次性发起整年并发聚合,5×3×2=30 次重试全失败,删完合成数据后 0 行入库 | 改为 `aggregate_array('system:time_start')` 一次列日期 + 逐图串行 `reduceRegion` + 0.4s 节流 (`3ea80d0`) |
| EVI 入库 0 行 | EVI reducer 用裸 `mean()`,EE 返回键 `EVI` 而非 `EVI_mean`,parser 拿 None 跳过 | EVI reducer 改 `mean.combine(min).combine(max)` 强制后缀 (`3ea80d0`) |
| 重跑产生重复 | `eco_indicators` 无 UNIQUE 约束,`ON CONFLICT DO NOTHING` 失效 | DELETE 同时清 `MODIS_synthetic` + `MODIS_GEE` (`3ea80d0`) |

### 安全回退

- 备份表 `regions_bbox_backup_20260518` 保留 bbox 矩形原值,如真实多边形渲染异常可一键回退:
  `UPDATE regions r SET bbox_json = b.bbox_json FROM regions_bbox_backup_20260518 b WHERE r.id = b.id;`

### 剩余 milestone 2️⃣ 工作

- [ ] `fetch_all_gee.py` 同步打 GEE 串行补丁,跑 LST + SMAP (2000-2026)
- [ ] NDVI/EVI 历史延伸到 2000-2019 (~20 年 × 23 张 × 2 区域 ≈ 30-40 分钟)
- [ ] 评估是否真要替换为 NESDC 官方矢量(当前 MODIS-derived 已退役 bbox)

---

*版本：v1 | 拟稿日期：2026-05-18 | 基线 commit：e6a75c8 + 本次修复*
*版本：v2 | 续修日期：2026-05-18 | 新增 commit：`3ea80d0` + 数据态变更(无代码 diff)*

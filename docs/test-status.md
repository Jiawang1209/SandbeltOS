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
| **LLM provider 已下线** | 任何提问 → "Error code: 422 - {'code': 422, 'message': '模型已下线'}" | 中科院 uni-api 上的 `qwen3:235b` 模型已下线（早先保存的 Caragana 对话仍可读，证明历史时点可用）。RAG 检索仍工作（每问拉回 5 条 0.4–0.93 score 的相关文献） | 切到可用 LLM endpoint，或换模型名 |
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

## 四、文档漂移（应顺手修）

| 位置 | 现状 | 应改 |
|---|---|---|
| `frontend/.../SiteFooter`（页脚） | "Ver. Phase 4 · RAG-powered Copilot" | "Ver. Phase 5 · Prediction & Scenario" 或不再标版本 |
| `chat` 右侧栏实时指标 | FVC 显示 `null%` | 后端 FVC 缺值时前端应渲染 "—" 或隐藏 |
| `README.md` 步骤 4 | 提示 `conda install ... redis-server` | 在 macOS 上 `conda-forge::redis-server` 装不到，README 应指引 `brew install redis` 或 `conda install -c conda-forge redis` |
| `README.md` 步骤 4 | 建议 conda PostgreSQL | 实际跑的是 Homebrew Postgres 16，README 应给两种路径 |

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

*版本：v1 | 拟稿日期：2026-05-18 | 基线 commit：e6a75c8 + 本次修复*

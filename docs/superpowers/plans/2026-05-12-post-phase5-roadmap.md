# Phase 5 之后 — 后续路线图

> 创建日期：2026-05-12
> 最近更新：2026-05-19
> 上游：Phase 5（预测 + 情景）已完成,见 [`2026-05-12-phase5-prediction-plan.md`](2026-05-12-phase5-prediction-plan.md)
> 基线 commit：Phase 5 收尾 + bbox_json hotfix 已合入主线
>
> **状态速览(2026-05-19):**
> - 1️⃣ 端到端验证:1.1 deferred · 1.2 ✅ · 1.3 ✅ · 1.4 deferred(user-side)· 1.5 ✅
> - 2️⃣ 真实 GEE 数据:2.1-2.5 ✅ · 2.6 ✅ · 2.7 ⏳ · 2.8 ⏳ · UI charts(LST/SMAP)✅
> - 3️⃣ Phase 3/4 收尾:⏳
> - 4️⃣ CI workflow:✅ `07f99f8`
> - 5️⃣ RAG 质量评估:✅ `f3954de` + `74c9925`
> - 6️⃣ 文档收敛:in-progress

---

## 0. 现状盘点

**叙事完成度:** 五件套(地图 / 指标 / RAG / 预测 / 情景)齐全,对外能演示。

**核心债务（按风险高低）:**

| 标签 | 债务 | 风险 |
|------|------|------|
| **诚信** | 所有数据仍是合成数据,前端有"演示数据"水印 | 演示时被追问"这是真的吗"难答 |
| **韧性** | 端到端从干净环境从未验证过(`bbox_json` 漏洞就是例证) | 重新部署随时翻车 |
| **完成度** | PLAN.md Phase 3 完成标志 3 项未勾,Phase 4 完成标志 3 项未勾 | "标 🟡 是因为 X 没做"问不清楚 |
| **质量门** | 47 commit 没 CI,schema drift 类问题没拦住 | 后续协作 / 重构会回归 |
| **文档膨胀** | ARCHITECTURE(39KB) + PLAN(17KB) + 4 份部署文档(~70KB) | 文档增长 > 代码增长,维护成本累积 |

**下一步原则:** 先固化 → 再质变 → 再扩展。
不要在合成数据上继续叠功能,把"已知能跑"先冻成一个基线 baseline。

---

## 1. 强烈推荐:1 → 2 这个顺序

### 1️⃣ 端到端验证 + demo 录制(1-2 天)

**目标:** 把整个系统从干净环境完整跑一遍 → 录段 2-3 分钟视频固化基线。

**为什么:**
- 整个项目从未在独立的干净环境里被验证过。`bbox_json` 那个洞已经证明,只要换个库就崩。
- 任何深入改造之前,先有一段"已知能跑"的实物视频。这既是对外演示素材,也是回归测试基线——日后改东西崩了一对照视频立刻知道。

**具体步骤:**

| # | 动作 | 验收 | 状态 |
|---|------|------|------|
| 1.1 | 在干净的 conda env 或 docker 重新走一遍 README 「快速开始」 | 五步全过,不需要任何"补丁"动作 | ⏳ deferred(用户偏好复用现有 env) |
| 1.2 | 跑完整 pytest suite(单元 + 集成),记每个失败/skip 的原因 | 输出测试报告,记入 `docs/test-status.md` | ✅ 118/118 green |
| 1.3 | 浏览器手测 5 个核心动作 | 见下方清单 | ✅ chrome-devtools MCP 实测通过 |
| 1.4 | 录 2-3 分钟视频(QuickTime / OBS) | 上传到项目本地 `docs/demos/` 或外部链接 | ⏳ user-side,SOP at `docs/demos/RECORDING_SOP.md` |
| 1.5 | 修录制中暴露的所有 bug,录第二遍 | 视频里没明显卡顿/报错 | ✅ bug fixes 合入主线 |

**视频里要展示的 5 个核心动作:**

1. 打开仪表盘 → 看到双沙地多边形 + 风险卡 + NDVI 趋势
2. 点击科尔沁 → 单沙地视图 + NDVI 图右侧延伸出绿色预测虚线 + 浅绿置信带 + 角标"演示数据"
3. 拖动情景面板控件:**柠条 500/ha 5 年 → 杨树 2000/ha 5 年**,看两条曲线对比剧变
4. 切到 `/chat`,问"科尔沁沙地杨树高密度造林有什么风险?",看流式 token + 引用来源
5. 切回地图,切到"对比" Landsat 模式,拖 2015 vs 2024 滑块

**录制小贴士:**
- 关闭通知 / 全屏浏览器
- 录前预热一次:Prophet 第一次 fit 慢,提前调用一遍让 Redis 缓存住
- 旁白用文字字幕(后期加)而不是语音,避免重录成本

### 2️⃣ 真实 GEE / ERA5 数据接入(3-5 天)

**目标:** 把 `eco_indicators` / `weather_data` 表里的合成数据**完全替换**为真实遥感观测,摘掉"演示数据"水印。

**为什么:** 这是从"demo"到"产品"的跨越。一旦真实数据进来:
- Prophet 不再是"把合成器外推一次",预测有真实物理意义
- 情景模型的经验常数可以基于真实历史校准
- RAG 问答里的实时指标变成真实区域状态
- 风险评估输出有可信度

**前置准备:**
- 确认 `.env` 里 `gee_project` (`ee-yueliu19921209`) 账号已激活,`secrets/gee-key.json` 服务账号 key 在位
- 确认 CDS API key (`cds_key`)已经在 `.env` 配上

**具体步骤:**

| # | 动作 | 工具/脚本 | 验收 | 状态 |
|---|------|---------|------|------|
| 2.1 | GEE 拉 MODIS NDVI/EVI(科尔沁 + 浑善达克,2015-2025) | `scripts/fetch_real_gee.py` 或 `fetch_all_gee.py` | `SELECT count(*) FROM eco_indicators WHERE source = 'MODIS'` ≥ 200 | ✅ 603 rows(2000-2026) |
| 2.2 | GEE 拉 MOD11A2 LST(地表温度) | `fetch_all_gee.py` 或自己加一支 | 表里 `indicator = 'lst'` 行数 > 0 | ✅ 1203 rows |
| 2.3 | GEE 拉 SMAP 土壤水分 | `fetch_all_gee.py` 或新支 | 表里 `indicator = 'soil_moisture'` 行数 > 0 | ✅ 124 rows |
| 2.4 | CDS 拉 ERA5(降水/风速/温度,2015-2025) | `scripts/fetch_era5_resume.py`(断点续传版,大文件友好) | `SELECT count(*) FROM weather_data` ≥ 1000 | ✅ 1827 × 2 regions |
| 2.5 | 真实数据进来后**重跑** `compute_risk.py` 让风险评估表用真值 | `scripts/compute_risk.py` | `desertification_risk` 表有新行,旧合成行可选清除 | ✅ done |
| 2.6 | 真实数据上重跑 Prophet 一次,看输出合不合理 | `curl /api/v1/prediction/ndvi-forecast?region_id=1&horizon=12` | yhat 在 [0.15, 0.45] 这个三北区合理 NDVI 区间 | ✅ yhat in range |
| 2.7 | 真实降水/风速进来后**重新校准** `scenario.py` 经验常数 | 手动调 `SM_DEFICIT_COEF` / `EFFECTIVE_PRECIP_FRACTION` 让 5 年情景对杨树/柠条的差异化仍合理 | 重跑 `pytest tests/test_scenario.py` 仍 12/12 过 | ⏳ pending |
| 2.8 | **摘掉前端"演示数据"角标** | 编辑 `dashboard/page.tsx` 移除 `<DemoDataBadge>` 引用,或加条件:`if (process.env.NEXT_PUBLIC_DEMO_MODE === 'true')` 才显示 | 默认显示无水印,可通过 env 重新打开作为退路 | ⏳ pending |
| 2.bonus | **Dashboard 加 LST/SMAP 图表 + KPI 卡** | `frontend/src/components/LstSmapChart.tsx` + dashboard KPI 行扩 3→5 | 单区视图同时展示 NDVI/LST/SMAP | ✅ `36eff27` + `b838b23` |

**潜在坑:**

| 风险 | 缓解 |
|------|------|
| GEE 配额满 / 大区域请求超时 | 分区域 + 分年度小批量拉,加 sleep + 指数退避 |
| ERA5 下载慢(CDS 排队几小时) | 用 `fetch_era5_resume.py` 断点续传,或改用 GEE 上的 ERA5-Land |
| 真实数据进来后情景模型常数失真 | 先 `git stash` 老校准,试新数据,不行就回滚常数 |
| 真实数据稀疏区域(MODIS 云遮挡) | 加质量过滤 `quality >= 1`,或线性插值小段缺口 |

---

## 2. 备选(都是 1-2 天能做完的小目标)

按"投入产出比"排序,不必照顺序做:

### 3️⃣ Phase 3 / 4 盘点收尾(1-2 天)

PLAN.md 里这两个标 🟡,但"完成标志"里有些 [ ] 没勾。两个出路:
- **要么补完,翻 ✅**(具体补什么:Phase 3 还差 Prefect 调度 + 4 指标卡 + 风险图层切换;Phase 4 还差预设快捷问题 + 引用展开)
- **要么诚实把目标拆分**:把已完成的归入 ✅,未做的拆到「后续扩展」段

**为什么要做:** 演示时被问"Phase 3 是黄色什么意思",回答"我们用 50 个 commit 完成了 80%,剩下的 20% 拆到这里"比说"我也不记得了"专业一百倍。

### 4️⃣ CI workflow(0.5 天)— ✅ `07f99f8`

加 `.github/workflows/ci.yml`,触发 push to main + pull_request:
- **frontend job**: `npx tsc --noEmit` + `npx eslint` (no DB, ~1 min)
- **backend job**: TimescaleDB-HA service container → `init.sql` → `scripts.seed_data` → `pytest -m "not slow"` (~5-8 min)

Slow tests(bge-m3 / bge-reranker / Prophet,要 ~2.5GB 模型下载)有意跳过,后面可加 scheduled / label-triggered 配套 workflow。

### 5️⃣ RAG 真实质量评估 — ✅ `f3954de` + `74c9925`

新增离线评测 CLI:`backend/scripts/eval_rag.py`,生成 markdown 报告。

**已落地:**
- golden_qa.yaml 从 10 题扩到 **20 题**,12 份 PDF 全部至少被 1 题命中
- CLI 输出每题 recall@1/@3/@5、MRR、关键词覆盖率,聚合 + 按 `Chunk.category` 分类 first-hit breakdown
- `--no-rerank` flag 用来对比 dense-only baseline,验证 bge-reranker 的增益
- 跑法:`docker compose exec backend python -m scripts.eval_rag --out /app/eval_report.md`

**尚未做:**
- LLM 答案质量人工打分(需要等 LLM endpoint 稳定 + 真实问答跑通后再做)
- chunk_size / top_k / prompt few-shot 迭代调优(等评测出第一份基线后再说)

### 6️⃣ 文档收敛(0.5-1 天)

当前重复 / 冗余 / 过时:
- `ARCHITECTURE.md` §8 的 prediction 代码模板已经过时(实际代码用了不同的函数名),只留一句"实际见 `services/prediction.py`"
- `PLAN.md` 和 `ARCHITECTURE.md` 有 70% 内容重叠的「技术栈」「目录结构」,合并一份
- 4 份部署文档(`DEPLOYMENT.md` / `DEPLOY_FRESH.md` / `deploy-demo.md` / `docker.md`)收敛到 2 份:「一键 Docker(`docker.md`)」+「完整生产(`DEPLOYMENT.md`)」

**收益:** 你写代码改一行,要改 5 个文档的现象消失。

---

## 3. 推荐执行节奏

```
本周（2026-05-12 ~ 2026-05-19）:
  Day 1-2  → 1️⃣ 端到端验证 + demo 录制
  Day 3    → 4️⃣ CI workflow（半天搞定）
  Day 4-7  → 2️⃣ 真实 GEE 数据接入（最大块）

下周（2026-05-19 ~ 2026-05-26）:
  Day 1-2  → 2️⃣ 收尾(数据稳定后重新校准 + 角标摘除)
  Day 3-4  → 3️⃣ Phase 3/4 盘点
  Day 5    → 5️⃣ RAG 质量评估
  Day 6-7  → 6️⃣ 文档收敛 + 整理,准备下一阶段
```

**关键里程碑(到达后可对外宣传):**
- 2026-05-13 (周三): 「能复现的演示视频」
- 2026-05-19 (周二): 「真实数据驱动的全链路」
- 2026-05-26 (周一): 「Phase 0-5 全部 ✅」

---

## 4. 不在当前计划内

以下功能继续放在 PLAN.md「后续扩展」段,**不必现在动**:

- 扩展区域(毛乌素、塔克拉玛干南缘、黄土高原)
- Sentinel-2 10m 高分辨率 NDVI
- 用户认证(JWT + 多用户)
- 造林树种推荐 ML(基于降水 × 土壤 × 立地)
- ChromaDB → Qdrant 迁移
- 困难立地分级专题
- 部署到云 + Nginx + HTTPS(虽然部署文档已经写了,真正部署需要时再走)
- LSTM 预测(Phase 5 已正式砍掉,真实数据进来后再评估是否回收)

---

## 5. 何时回来更新这个文档

- 每完成一项,把对应章节标 ✅ 并记 commit hash
- 真实数据接入后,回 [`2026-05-12-phase5-prediction-plan.md`](2026-05-12-phase5-prediction-plan.md) 的「风险清单」逐条核对哪些缓解动作真的需要触发
- 走到下周路线图末尾时,新建 `2026-05-26-roadmap-v2.md`,把这份归档

---

*本路线图版本:v1 | 拟稿日期:2026-05-12 | 基于 Phase 5 收尾后的项目状态*

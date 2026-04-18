# Phase 4 — RAG 智慧问答系统设计

**Date:** 2026-04-18
**Author:** Brainstormed via Claude (superpowers:brainstorming)
**Status:** Draft → User Review
**Scope:** SandbeltOS Phase 4（智慧问答模块），不涉及 Phase 5+

---

## 1. 目标

给 SandbeltOS 增加一个自然语言问答模块，让用户能用中文提问三北防护林 / 科尔沁沙地 / 浑善达克沙地相关问题，系统结合 **(a) 已策划的学术文献语料** 与 **(b) 当前实时传感器指标**（NDVI / 风险等级 / 天气 / 土地覆盖），生成带引用的回答。

MVP 成功标准：
- 10 道 Golden 问题中，≥8 道回答正确（引用正确文献 + 关键数值与结论一致）
- 普通问答端到端首 token 延迟 <2s，全部回答完成 <10s
- `/chat` 全屏页 + Dashboard 浮窗两个入口都可用，共用后端

非目标（显式排除）：
- 多轮对话记忆（MVP 单轮即可；每次问题独立检索）
- 用户账号 / 对话历史持久化
- 图表生成、代码执行类 agent 能力
- 实时数据写入（只读）

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 14 App Router)                           │
│  ┌────────────────────┐       ┌───────────────────────────┐ │
│  │  /chat 全屏页       │       │  Dashboard 右下角浮窗       │ │
│  │  (SourcesPanel +    │       │  (紧凑、pill 式来源、        │ │
│  │   MetricsPanel)     │       │   region 自动注入)          │ │
│  └─────────┬──────────┘       └─────────────┬─────────────┘ │
│            └─────────── useChat() ──────────┘               │
└────────────────────────┬────────────────────────────────────┘
                         │ POST /api/v1/chat (SSE)
┌────────────────────────▼────────────────────────────────────┐
│  FastAPI — backend/app/api/v1/chat.py                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 1. query_router.parse(question)                        │ │
│  │ 2. 并行:                                                │ │
│  │    a) retriever.retrieve  (bge-m3 → Chroma top-20)      │ │
│  │    b) live_metrics.fetch_snapshot (若需要)              │ │
│  │ 3. reranker.rerank (bge-reranker-v2-m3 → top-5)         │ │
│  │ 4. 组装 ECO_DECISION_PROMPT                             │ │
│  │ 5. Claude Sonnet 4.6 streaming                          │ │
│  │ 6. SSE events: sources → metrics → token* → done        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌───────────────┐          ┌──────────────────┐
│  ChromaDB     │          │  PostGIS / 指标   │
│  (本地向量)    │          │  services (已有)  │
└───────────────┘          └──────────────────┘
```

**关键决策**：检索与实时指标获取**并行**；rerank 只依赖 retrieval 返回，不阻塞 metrics；LLM 只看 top-5 + 最新传感器快照，控制 token。

---

## 3. 语料

MVP 语料 12 篇 PDF，`backend/rag/docs/` 下：

| 类别 | 数量 | 关键文献 |
|---|---|---|
| `gov/` | 1 | three-north-scientific-greening-strategy（科学绿化策略） |
| `papers_cn/` | 1 | PKU 三北经济效益 |
| `papers_en/` | 10 | Horqin NE 土壤侵蚀、浑善达克固沙林、Caragana 抗旱、Populus 水分、RWEQ 风蚀方法、NPP 干旱响应、温带草原物种多样性、NW 中国碳固定、Alxa 土壤水 |

**主题覆盖**：Horqin ✓ / Hunshandake ✓ / 风蚀 RWEQ ✓ / NDVI-NPP 动态 ✓ / 造林物种 ✓ / 土壤水碳 ✓ / 政策 ✓

**扩充机制**：若 Golden 题目暴露盲区，定向通过浏览器手动下载补充（MDPI 等源被反爬）。新增 PDF 放入目录后重跑 `python -m backend.rag.ingest --incremental` 即可。

---

## 4. 检索层

### 4.1 Ingest (`backend/rag/ingest.py`)

- 用 **PyMuPDF** 抽 PDF 文本，保留 `page_number`
- 用 **langchain `RecursiveCharacterTextSplitter`** 切块：
  - `chunk_size=800` 字符，`chunk_overlap=100`
  - 分隔符优先级：`["\n\n", "\n", "。", "！", "？", ". ", " "]`（中文友好）
- 每个 chunk 元数据：
  ```python
  {
    "source": "2024_hunshandake_sand_fixation_plantations.pdf",
    "title": "Sand Fixation Plantations ...",
    "category": "papers_en",
    "page": 4,
    "lang": "en",          # "en" | "zh"（自动识别）
    "region_hint": ["hunshandake"],   # 从文件名/标题预解析
  }
  ```
- 12 篇预估 **~3,000 chunks**，Chroma 存储 <500MB
- 支持 `--rebuild` 一键重建、`--incremental` 只处理新增 PDF

### 4.2 Embedding (`backend/rag/embedder.py`)

```python
from FlagEmbedding import BGEM3FlagModel
model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
```

- 离线模型 ~2.3GB，缓存在 `~/.cache/huggingface/`
- 设备自动检测：`mps`（Mac）/ `cuda` / `cpu`
- 首次 ingest 约 5-10 min；之后增量
- 只存 dense vector（1024d）；sparse 留日后混合检索用

### 4.3 向量库

```python
chroma = chromadb.PersistentClient(path="backend/rag/chroma_store")
col = chroma.get_or_create_collection(
    name="sandbelt_corpus",
    metadata={"hnsw:space": "cosine"},
)
```

`backend/rag/chroma_store/` 加入 .gitignore。

### 4.4 Retrieval + Rerank (`backend/rag/retriever.py` + `reranker.py`)

```python
def retrieve(query: str, region: str | None, top_k: int = 5):
    # 1) dense 召回 top-20，带元数据过滤
    q_emb = embedder.encode(query)
    candidates = col.query(
        query_embeddings=[q_emb],
        n_results=20,
        where={"region_hint": {"$contains": region}} if region else None,
    )
    # 2) bge-reranker-v2-m3 重排
    pairs = [(query, c["text"]) for c in candidates]
    scores = reranker.compute_score(pairs, normalize=True)
    return sorted(zip(candidates, scores), key=lambda x: -x[1])[:top_k]
```

- reranker 模型 `BAAI/bge-reranker-v2-m3`，~600MB
- 延迟：top-20 rerank CPU ~300ms / M1 mps ~80ms

---

## 5. 查询路由 + 实时指标注入

### 5.1 Query Router (`backend/app/services/query_router.py`)

纯关键词匹配，无 LLM：

```python
REGION_KEYWORDS = {
  "horqin":      ["科尔沁", "Horqin", "horqin", "通辽", "奈曼"],
  "hunshandake": ["浑善达克", "Hunshandake", "Otindag", "锡林郭勒"],
}
INTENT_KEYWORDS = {
  "current_status": ["现在", "当前", "目前", "now", "current"],
  "trend":          ["趋势", "变化", "近.*年", "trend"],
  "risk":           ["风险", "危险", "risk", "alert"],
  "species":        ["树种", "植被", "species", "plantation"],
  "method":         ["怎么算", "公式", "方法", "RWEQ", "FVC"],
}

@dataclass
class QueryContext:
    regions: list[str]
    intents: list[str]
    needs_live_data: bool   # regions 非空 且 intents ∩ {current_status, risk, trend} 非空
```

### 5.2 Live Metrics (`backend/rag/live_metrics.py`)

只在 `needs_live_data=True` 时调用；复用已有 service 函数（不走 HTTP）：

```python
async def fetch_snapshot(region_id: str) -> dict:
    # 注：下列函数名为示意。Sprint 1 首先要把 backend/app/api/v1/ecological.py
    # 的路由处理逻辑抽到 backend/app/services/ecological.py（纯函数，不依赖
    # FastAPI Request），再在这里调用，避免走 HTTP。
    ndvi, risk, weather, landcover, alerts = await asyncio.gather(
        ecological_svc.get_current_status(region_id),
        ecological_svc.get_risk_latest(region_id),
        ecological_svc.get_weather_latest(region_id),
        ecological_svc.get_landcover_latest(region_id),
        ecological_svc.get_alerts(region_id, limit=1),
    )
    return {
        "region": region_id,
        "timestamp": ndvi["timestamp"],
        "ndvi": ndvi["value"],
        "fvc": ndvi["fvc"],
        "risk_level": risk["level"],            # 1-4
        "wind_speed": weather["wind_speed"],    # m/s
        "soil_moisture": weather["soil_moisture"],  # %
        "last_alert": alerts[0] if alerts else None,  # {level, message, timestamp}
    }
```

---

## 6. Generation 层

### 6.1 Prompt (`backend/rag/prompt_templates.py`)

```python
ECO_DECISION_PROMPT = """你是三北防护林生态决策助手 SandbeltOS。回答时必须：
1. 基于下方【文献】和【实时指标】给答案，不要编造
2. 用 [1] [2] 格式引用文献（对应 Sources 列表顺序）
3. 当【实时指标】与【文献】结论冲突时，指出冲突并以实时数据为准
4. 中文回答，简洁、不啰嗦、直接给结论+证据

【用户问题】
{question}

【实时指标】(若可用)
{live_metrics_block}

【文献片段】
{retrieved_chunks_block}

【回答要求】
- 先给 1-2 句核心结论
- 然后给关键证据（引用 [n]）
- 如果涉及数值，必须明确时间/地点
- 最后如果有不确定性，诚实说明
"""
```

- `live_metrics_block`：key-value 表格式文本；不可用时整块省略（prompt 里也省略对应行）
- `retrieved_chunks_block`：每段前加 `[1] <title, page>` 便于 LLM 引用

### 6.2 SSE Endpoint (`backend/app/api/v1/chat.py`)

```python
@router.post("/chat")
async def chat(req: ChatRequest):
    ctx = query_router.parse(req.question)

    chunks_task = asyncio.create_task(
        retriever.retrieve(req.question, ctx.regions[0] if ctx.regions else None)
    )
    metrics_task = asyncio.create_task(
        live_metrics.fetch_snapshot(ctx.regions[0])
    ) if ctx.needs_live_data else None

    chunks = await chunks_task
    metrics = await metrics_task if metrics_task else None

    prompt = ECO_DECISION_PROMPT.format(...)
    sources = [
        {"id": i+1, "title": c.title, "page": c.page, "source": c.source}
        for i, c in enumerate(chunks)
    ]

    async def event_stream():
        yield sse("sources", json.dumps(sources))
        if metrics:
            yield sse("metrics", json.dumps(metrics))
        async for delta in claude_stream(prompt):
            yield sse("token", delta)
        yield sse("done", "")

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

**SSE 事件类型**：`sources`（一次）/ `metrics`（一次）/ `token`（增量）/ `done`（结束）。

### 6.3 Claude 配置

- 模型：`claude-sonnet-4-6`
- Max tokens：2048
- 重试：`anthropic` SDK 自带；前端显示节流态，不丢已流出的 token

---

## 7. UI

### 7.1 共享 Hook (`frontend/src/hooks/useChat.ts`)

```tsx
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);

  async function ask(question: string, regionHint?: string) {
    // 1. 追加 user + empty assistant 消息
    // 2. fetch POST /api/v1/chat (SSE)
    // 3. 解析 SSE 事件：
    //    - sources → messages[last].sources = ...
    //    - metrics → messages[last].metrics = ...
    //    - token   → messages[last].content += delta
    //    - done    → setStreaming(false)
  }

  return { messages, streaming, ask };
}
```

两个入口共用 hook，对话状态在同一 React 树内同步；路由切换时不共享（MVP 可接受）。

### 7.2 `/chat` 全屏页 (`frontend/src/app/chat/page.tsx`)

布局：
- 左栏（flex-1）：对话流，markdown 渲染 + `[n]` 可点击跳右栏高亮
- 右栏（320px）：**引用来源面板**（卡片式）+ **实时指标面板**（指标表）
- 底部：输入框，Enter 发送 / Shift+Enter 换行；流式中禁用
- Header：新对话按钮（清空 messages）

**空状态**：6 个示例问题（按主题分：风险评估 / 指标解释 / 历史对比 / 物种选择 / 政策 / 方法论）。

### 7.3 Dashboard 浮窗 (`frontend/src/components/ChatWidget.tsx`)

- 始终可见的圆形浮钮（右下角固定定位）
- 展开尺寸：宽 400px / 高 60vh
- 紧凑布局：来源/指标不占独立侧栏，用 pill + hover 浮卡
- 右上角 ⤢：跳转到 `/chat` 全屏（MVP 不跨入口延续对话，仅跳转）
- **region 自动注入**：Dashboard 通过 `regionHint` prop 把**用户最后交互的 RegionMap 对应的 region_id**（`horqin` | `hunshandake`）传给 `<ChatWidget />`，widget 调 `ask(q, regionHint)` 时自动注入。对比模式下取 primary region（左侧地图）
- `dynamic(() => import, { ssr: false })` 不阻塞 Dashboard 首屏

### 7.4 视觉 & 交互

- 流式打字：token 到达即 append
- Sources 提前出现：答案第一个字前就显示，给"在找资料了"的信号
- Metrics 卡片：fade-in + 数字 tween
- 错误态：Claude 429 时显示"节流中，3s 后自动重试"，不丢已流出的 token
- Accessibility：Tab 可循环焦点；ESC 关闭浮窗

---

## 8. 测试

### 8.1 Unit

- `tests/test_chunker.py` — 中文不切坏句子；英文 abstract 独立成块
- `tests/test_query_router.py` — "科尔沁"→horqin；"RWEQ"→method（不拉 live）
- `tests/test_prompt_builder.py` — sources 顺序稳定；live_metrics 为空时不留空槽

### 8.2 Integration

- `tests/test_retriever.py` — 小语料夹具（3 篇），top-5 必含预期来源
- `tests/test_chat_endpoint.py` — Mock Claude，验证 SSE 事件顺序 sources→metrics→token→done

### 8.3 Golden 集 (`tests/golden_qa.yaml`)

10 道题；对每题断言：
- 必含来源（文件名白名单）
- 回答必含关键词
- 回答长度 100-500 字

题目清单：
1. 科尔沁沙地近 20 年 NDVI 趋势怎样？
2. 浑善达克风险等级现在是多少？为什么？
3. RWEQ 公式怎么算？用了哪些输入？
4. Caragana korshinskii 适合在哪些区域造林？
5. 三北防护林科学绿化策略的核心原则？
6. 为什么 2022 年 NE 内蒙古土壤侵蚀下降？
7. 浑善达克的固沙林对土壤性质有何影响？
8. Populus simoni 在辽宁沙地表现如何？
9. 怎样判断一个区域是否已沙化？
10. 实时数据显示科尔沁 NDVI 0.3，算偏低吗？（考 live + 文献联合推理）

### 8.4 E2E (Playwright)

- `e2e/chat.spec.ts` — `/chat` 打字 → token 流出 → 来源栏渲染
- `e2e/widget.spec.ts` — Dashboard 浮窗展开 / region 自动注入 / ⤢ 跳 `/chat`

覆盖率目标：核心模块 ≥80%（参考 common/testing.md）。

---

## 9. 配置 & 部署

### 9.1 环境变量（新增到 `.env`）

```bash
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_MAX_TOKENS=2048
CHROMA_PERSIST_DIR=backend/rag/chroma_store
RAG_EMBEDDER=BAAI/bge-m3
RAG_RERANKER=BAAI/bge-reranker-v2-m3
RAG_TOP_K_RETRIEVE=20
RAG_TOP_K_RERANK=5
RAG_CHUNK_SIZE=800
RAG_CHUNK_OVERLAP=100
```

### 9.2 依赖（`backend/requirements.txt` 新增）

```
FlagEmbedding>=1.2.10
chromadb>=0.4.22
anthropic>=0.34.0
PyMuPDF>=1.24.0
langchain-text-splitters>=0.2.0
```

### 9.3 首次部署流程

```bash
pip install -r backend/requirements.txt
python -m backend.rag.ingest                 # 首次 5-10 min
uvicorn backend.app.main:app --reload
cd frontend && pnpm install && pnpm dev
```

### 9.4 .gitignore 新增

```
backend/rag/chroma_store/
backend/rag/docs/*.pdf
backend/rag/docs/manifest*.json
backend/rag/docs/download*.log
```

---

## 10. 开发顺序（5 个 Sprint，5-7 天）

| Sprint | 交付 | 预估 |
|---|---|---|
| **1. 检索管道** | `ingest.py` + `embedder.py` + `retriever.py` + CLI 冒烟 + unit 测试 | 1-2 天 |
| **2. Rerank + Router + Live** | `reranker.py` / `query_router.py` / `live_metrics.py` + unit 测试 | 1 天 |
| **3. SSE Endpoint** | `prompt_templates.py` / `app/api/v1/chat.py` + Mock Claude 测试 + 真实冒烟 | 1 天 |
| **4. `/chat` 全屏页** | `useChat` hook / ChatMessage / Sources / Metrics + Playwright E2E | 1-2 天 |
| **5. Dashboard 浮窗 + Golden 验收** | `ChatWidget` / region 注入 / ⤢ 跳转 / 10 题 golden 人工 review | 1 天 |

每 Sprint 完成点：绿灯测试 + code-reviewer 扫一遍 + commit。

---

## 11. 风险 & 缓解

| 风险 | 缓解 |
|---|---|
| bge-m3 首次下载 2.3GB 卡住 | `ingest.py` 开头日志提示 & 支持离线代理变量 |
| 中文 chunking 切坏句子 | 已用 `。！？` 分隔；Golden 抽查 |
| Claude API 429 / 超时 | `anthropic` SDK 自带重试；前端显示节流态，不丢 token |
| 只 12 篇语料 → 某些问题答不好 | Golden 暴露盲区后定向补文献 |
| Live metrics 慢（>500ms）| 已有 service 缓存；SSE 先推 sources 让用户感知"在思考" |
| Chroma 文件损坏 | `ingest.py --rebuild` 一键重建 |
| Dashboard 首屏被浮窗拖慢 | `dynamic(ssr: false)` 不阻塞 LCP |

---

## 12. 未覆盖 / 后续迭代

显式推到 Phase 5+：
- 多轮对话记忆（conversation id + DB 存储）
- 用户账号 + 个人对话历史
- 跨入口对话延续（点击 ⤢ 带着 widget 对话进 /chat）
- 混合检索（bge-m3 dense + sparse + BM25 融合）
- 引用可信度分数 / reranker 阈值过滤
- 中文 OCR（PDF 是扫描件时）
- Agent-style 工具调用（自动画图、查 DB、跑分析）
- 多模态（上传截图提问）

---

## 13. 新增文件清单

**Backend 新增（14）**：
- `backend/rag/embedder.py`
- `backend/rag/reranker.py`
- `backend/rag/ingest.py`
- `backend/rag/retriever.py`
- `backend/rag/live_metrics.py`
- `backend/rag/prompt_templates.py`
- `backend/app/api/v1/chat.py`
- `backend/app/services/query_router.py`
- `backend/app/services/ecological.py`（从 `api/v1/ecological.py` 抽纯函数）
- `backend/tests/test_chunker.py`
- `backend/tests/test_query_router.py`
- `backend/tests/test_prompt_builder.py`
- `backend/tests/test_retriever.py`
- `backend/tests/test_chat_endpoint.py`
- `backend/tests/golden_qa.yaml`

**Frontend 新增（7）**：
- `frontend/src/app/chat/page.tsx`
- `frontend/src/components/ChatWidget.tsx`
- `frontend/src/components/chat/SourcesPanel.tsx`
- `frontend/src/components/chat/MetricsPanel.tsx`
- `frontend/src/hooks/useChat.ts`
- `frontend/e2e/chat.spec.ts`
- `frontend/e2e/widget.spec.ts`

**修改（5）**：
- `backend/app/main.py`（注册 chat router）
- `backend/app/api/v1/ecological.py`（路由改为调用 services 层）
- `backend/requirements.txt`（新增依赖）
- `frontend/src/app/dashboard/page.tsx`（挂载 `<ChatWidget />`）
- `.env` / `.env.example`（新增变量）
- `.gitignore`（新增忽略）

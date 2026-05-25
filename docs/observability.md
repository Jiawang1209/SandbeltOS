# Observability

> 后端默认就装了 Sentry / Prometheus / slowapi（见 `7e37d13`），但 **可视化看板是 opt-in**：用 `obs` profile 把 Prometheus + Grafana 起起来。

---

## 一键起 Grafana

```bash
docker compose --profile obs up -d
```

打开 <http://localhost:3001>（默认 admin / admin，首次登入会要求改密码），左侧 **Dashboards → SandbeltOS** 文件夹里有自动 provision 的 **SandbeltOS API** 看板。

端口可通过 `.env` 改：

```env
PROMETHEUS_PORT=9090
GRAFANA_PORT=3001
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin    # 上线前务必改强密码
```

---

## 看板里有什么

`SandbeltOS API` (uid: `sandbeltos-api`) 9 个 panel，全部来自 backend `/metrics`（`prometheus-fastapi-instrumentator` 默认指标）：

| 区 | Panel | PromQL 核心 |
|---|---|---|
| 顶部 stat 行 | Backend Up | `up{job="sandbelt-backend"}` |
|  | Request Rate (5m) | `sum(rate(http_requests_total[5m]))` |
|  | Error Rate % (5xx) | `sum(rate(...status=~"5..")) / sum(rate(...))` |
|  | p95 Latency | `histogram_quantile(0.95, ...)` |
|  | Total Requests (1h) | `sum(increase(http_requests_total[1h]))` |
| 中部 | Request Rate by Route | `sum by (handler) (rate(http_requests_total[5m]))` |
|  | Latency Percentiles | p50 / p95 / p99 时序 |
| 底部 | Status Code Distribution | `sum by (status) (rate(...))`（2xx 绿 / 4xx 橙 / 5xx 红）|
|  | Top 10 Slowest Routes (p95, 15m) | `topk(10, histogram_quantile(0.95, ...))` |

刷新间隔 30s，默认窗口 `now-1h`。

---

## 排错

| 现象 | 原因 / 处理 |
|---|---|
| Grafana 起来但 panel 全是 "No data" | Prometheus 还没采到第一轮（15s scrape）；或者后端没收到流量。`curl http://localhost:8000/metrics` 看是否有 `http_requests_total` 系列 |
| `Backend Up` = DOWN | Prometheus 容器拼不到 `backend:8000`。`docker compose --profile obs logs prometheus` 看 scrape 错误 |
| 看不到自定义业务指标 | 当前只采 FastAPI HTTP 默认指标；要加业务 metric（GEE fetch 耗时、LLM token 用量等），在 `backend/app/` 里用 `prometheus_client.Counter/Histogram`，instrumentator 会自动一起暴露 |
| 想停掉 obs stack | `docker compose --profile obs down`（不带 `-v` 不会删 TSDB 数据） |

---

## 数据持久化

| 路径 | 内容 |
|---|---|
| `data/prometheus/` | Prometheus TSDB，保留 15 天（在 compose `--storage.tsdb.retention.time=15d`） |
| `data/grafana/` | Grafana SQLite（用户、面板修改、API key） |

`./observability/` 目录（provisioning 配置 + dashboard JSON）是只读挂载，所有改动通过 git 提交。

---

## Rate limiting

slowapi enforces both a global default and stricter per-route limits on
the two expensive endpoints. All limits are per-IP, in-memory (lost on
container restart — for clustered deploys, switch to the Redis storage
backend at `app/limiter.py`).

| Endpoint | Default | Reason |
|---|---|---|
| (everything else) | `API_RATE_LIMIT=100/minute` | Generous; protects against accidental burst loops |
| `POST /api/v1/chat` | `CHAT_RATE_LIMIT=20/minute` | Each call burns LLM tokens — real money |
| `POST /api/v1/prediction/scenario` | `SCENARIO_RATE_LIMIT=30/minute` | CPU-bound multi-year simulation |

To disable all limits (e.g. for `pytest -n auto`), set `API_RATE_LIMIT=`
empty — the limiter object stays but `enabled=False` short-circuits every
decorator including the per-route ones.

429 response body matches slowapi's default handler: `{"error":"Rate limit exceeded: <rule>"}`.

---

## Forecast cache pre-warming

Prophet NDVI fit is slow (~5-10s/region on real data). First dashboard visit
of the day pays the cost otherwise — script + boot hook keep cold-start off
the critical path.

**Two ways to warm:**

1. **Boot hook** — `.env`:
   ```env
   CACHE_WARM_ON_BOOT=true
   ```
   Backend startup spawns a non-blocking background task; uvicorn does not wait.

2. **Cron / Prefect / manual**:
   ```bash
   docker compose exec backend python -m scripts.warm_forecast_cache
   ```
   Flags:
   - `--region N` warm one region instead of all
   - `--horizon N` override default 12
   - `--dry-run` list what would be warmed
   - `-v` debug logs

Cache TTL is 30 min but the key includes today's date, so a daily 06:00 cron
hits Redis before the first user shows up. Idempotent — re-runs are cheap.

---

## Sentry

Sentry SDK 也在同一次 observability commit 里，但跟 Prometheus 解耦——只要 `SENTRY_DSN` 是空，SDK 不会初始化。要打开：在 [sentry.io](https://sentry.io) 建项目 → 拿到 DSN → 写到 `.env`：

```env
SENTRY_DSN=https://xxx@oXXX.ingest.sentry.io/YYY
SENTRY_TRACES_SAMPLE_RATE=0.0    # 错误优先；要 perf trace 再调到 0.1
```

重启 backend 即生效。

# SandbeltOS 服务器从零部署（数据全部在服务器上重新拉）

> **适用场景**：一台空白 Linux 服务器（Ubuntu 22.04/Debian 12 起步），想把整个系统直接跑起来，数据库从空开始、GEE/ERA5 数据在服务器上重新抓。**不涉及本地数据迁移、不涉及域名/HTTPS**。
>
> **预计时长**：首次 30–90 分钟，其中容器构建约 10 min、GEE 数据拉取 30–60 min（后台）。
>
> **服务器规格**：最低 2c4g / 60 GB；**推荐 4c8g / 100 GB**（RAG 的 bge-m3 冷加载 2.5 GB 内存）。

---

## 0. 准备清单（开始前确认）

| 项 | 说明 |
|---|---|
| 服务器 | Linux x86_64，有 root 或 sudo |
| 服务器公网 IP | 记作 `<SERVER_IP>` |
| 开放端口 | 安全组放行 `22` `3000` `8000` 的入站 TCP |
| GEE 服务账号 | 邮箱 + JSON key 文件（`sandbelt-gee@ee-yueliu19921209.iam.gserviceaccount.com` + `gee-key.json`） |
| LLM API Key | uni-api / OpenAI / 任何兼容的 key |
| 本地仓库 | `/Users/liuyue/Desktop/Github_repos/SandbeltOS/`（或已推 GitHub） |

CDS（ERA5 气象）Key 不是必需 — 没有也能跑，只是气象那块没数据。

---

## 1. 上传项目到服务器

选一种：

### 1A. 用 rsync（推荐，走本地代码）

```bash
# 本地执行
cd /Users/liuyue/Desktop/Github_repos/SandbeltOS

rsync -avz --progress \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='__pycache__' \
  --exclude='.next' \
  --exclude='data/' \
  --exclude='*.pyc' \
  --exclude='.venv' \
  ./ root@<SERVER_IP>:/opt/sandbelt/SandbeltOS/
```

> 关键是 `--exclude='data/'` —— 本地那份半成品数据库**不要带**，服务器上要干净起。

### 1B. 用 Git

```bash
# 服务器执行
mkdir -p /opt/sandbelt
cd /opt/sandbelt
git clone https://github.com/Jiawang1209/SandbeltOS.git
cd SandbeltOS
```

---

## 2. 上传 GEE 密钥（单独上传，不走 rsync）

```bash
# 本地执行，scp 上去
scp secrets/gee-key.json ubuntu@175.27.213.32:/opt/sandbelt/SandbeltOS/secrets/

# 服务器执行，锁权限
ssh root@<SERVER_IP>
chmod 600 /opt/sandbelt/SandbeltOS/secrets/gee-key.json
```

---

## 3. 在服务器上配置 `.env`

```bash
cd /opt/sandbelt/SandbeltOS

# 基于 .env.example 生成
cp .env.example .env
vim .env   # 按下表修改
```

**必填项**（其他保留默认即可）：

```ini
# === 数据库密码（务必改强） ===
POSTGRES_PASSWORD=换成一个至少 16 位的强密码

# === 数据库连接字符串里的密码，和上一行保持一致 ===
DATABASE_URL=postgresql+asyncpg://sandbelt:换成那个密码@postgres:5432/sandbelt_db
DATABASE_URL_SYNC=postgresql://sandbelt:换成那个密码@postgres:5432/sandbelt_db

# === Redis（Docker 内部名，不要改） ===
REDIS_URL=redis://redis:6379/0

# === GEE ===
GEE_SERVICE_ACCOUNT=sandbelt-gee@ee-yueliu19921209.iam.gserviceaccount.com
GEE_PROJECT=ee-yueliu19921209
GEE_KEY_FILE=/app/secrets/gee-key.json

# === LLM ===
LLM_BASE_URL=https://uni-api.cstcloud.cn/v1
LLM_API_KEY=你真实的 key
LLM_MODEL=deepseek-v3:671b

# === CDS（没有就留空） ===
CDS_KEY=

# === 前端 API 地址（关键！） ===
NEXT_PUBLIC_API_URL=http://<SERVER_IP>:8000

# === CORS（必须和上面前端地址匹配） ===
CORS_ORIGINS=http://<SERVER_IP>:3000

# === 环境 ===
APP_ENV=production
```

> ⚠️ `NEXT_PUBLIC_API_URL` 是**前端构建时注入**的，改了必须重 build 前端（见 §8）。
> ⚠️ `CORS_ORIGINS` 的端口、协议必须和浏览器访问地址完全一致，差一个字符都会跨域失败。

---

## 4. 一键起服务

仓库根目录自带 `deploy.sh`（会安装 Docker、校验 `.env`、构建镜像、启动容器）：

```bash
cd /opt/sandbelt/SandbeltOS
chmod +x deploy.sh
./deploy.sh
```

如果你服务器已经装好 Docker，可以跳过 Docker 安装这步：

```bash
SKIP_DOCKER_INSTALL=1 ./deploy.sh
```

**等待信号**：脚本结束时会显示

```
✔ postgres  healthy
✔ redis     running
✔ backend   healthy (GET /health = 200)
✔ frontend  running
```

此刻浏览器访问 `http://<SERVER_IP>:3000` 能打开页面，但**所有区域都是空的**——因为数据库是空的。下一步灌数据。

---

## 5. 灌数据（进 backend 容器跑脚本）

进入容器：

```bash
docker exec -it sandbelt-backend bash
# 接下来所有命令都在容器里跑，提示符变成 root@xxxx:/app#
cd /app
```

### 5.1 种区域边界（秒级）

```bash
python -m scripts.seed_region_polygons
python -m scripts.seed_accurate_sandy   # 科尔沁、浑善达克精细边界
```

跑完会看到 `regions` 表有记录。

### 5.2 先用服务账号登录 GEE（**关键！**）

仓库里的 `fetch_*` 脚本默认用**个人账号**初始化 GEE（`ee.Initialize(project=...)`）。容器里没有个人 credentials，所以要先用服务账号登录一次：

```bash
# 容器里执行
earthengine authenticate --service-account-file=/app/secrets/gee-key.json
```

> 如果这条命令的 CLI 不存在，直接跑 Python 也行：
> ```bash
> python -c "
> import ee
> creds = ee.ServiceAccountCredentials(
>   'sandbelt-gee@ee-yueliu19921209.iam.gserviceaccount.com',
>   '/app/secrets/gee-key.json')
> ee.Initialize(creds, project='ee-yueliu19921209')
> print('GEE service account OK')
> "
> ```
> 只要这段能打印 `OK`，下面的 fetch 脚本里 `ee.Initialize()` 也会用同一套凭据。

### 5.3 拉 GEE 遥感数据（慢，30–60 min，强烈建议后台跑）

```bash
# 容器里
nohup python -m scripts.fetch_all_gee > /tmp/gee.log 2>&1 &
echo $! > /tmp/gee.pid   # 记住进程号

# 看进度
tail -f /tmp/gee.log

# 结束后确认
ps -p $(cat /tmp/gee.pid) || echo "已结束"
```

会依次拉 MODIS NDVI/EVI、MODIS LST、SMAP 土壤湿度（2000–2026）。完成后 `eco_indicators` 表应该有几万行。

### 5.4 拉 ERA5 气象（可选）

有 CDS Key 才跑：

```bash
# 容器里
nohup python -m scripts.fetch_era5 > /tmp/era5.log 2>&1 &
tail -f /tmp/era5.log
```

### 5.5 计算沙化风险

GEE + ERA5 数据齐了之后：

```bash
python -m scripts.compute_risk
```

会写 `desertification_risk` 表和 `alerts` 表。

### 5.6 灌 RAG 知识库（可选）

如果有 PDF 语料要传：

```bash
# 先退出容器，本地把 PDF 传过去
exit
```

```bash
# 本地
rsync -avz backend/rag/docs/ root@<SERVER_IP>:/opt/sandbelt/SandbeltOS/data/rag_docs/
```

```bash
# 服务器上，让 backend 重建索引
ssh root@<SERVER_IP>
docker exec -it sandbelt-backend python -m rag.ingest --rebuild
```

> 首次跑会从 HuggingFace 下载 bge-m3 (~2 GB) 和 bge-reranker-v2-m3 (~600 MB)，耐心等。
> 没 PDF 就跳过，聊天会退化为无检索纯 LLM。

---

## 6. 验证

### 6.1 后端接口

```bash
# 服务器上
curl http://localhost:8000/health
# 期望：{"status":"ok"}

curl http://localhost:8000/api/regions | head -c 500
# 期望：返回区域列表 JSON

curl "http://localhost:8000/api/eco/trend?region_id=1&indicator=ndvi_mean" | head -c 500
# 期望：时序数据
```

### 6.2 前端页面

浏览器打开 `http://<SERVER_IP>:3000`，应该能看到：

- 首页区域选择器
- 点进某区域，NDVI/LST 时序图有数据
- 沙化风险面板有等级显示
- 若有 RAG 数据，"智能问答" tab 能正常对话

### 6.3 数据体检

```bash
docker exec -it sandbelt-postgres psql -U sandbelt -d sandbelt_db -c "
SELECT 'regions' AS t, count(*) FROM regions
UNION ALL SELECT 'eco_indicators', count(*) FROM eco_indicators
UNION ALL SELECT 'weather_data', count(*) FROM weather_data
UNION ALL SELECT 'desertification_risk', count(*) FROM desertification_risk
UNION ALL SELECT 'alerts', count(*) FROM alerts
UNION ALL SELECT 'afforestation_records', count(*) FROM afforestation_records;
"
```

正常情况：regions 几条、eco_indicators 几万到几十万、其它看具体拉取情况。

---

## 7. 常见问题速查

| 症状 | 原因 | 解决 |
|---|---|---|
| 前端 `Failed to fetch` / CORS 报错 | `NEXT_PUBLIC_API_URL` 或 `CORS_ORIGINS` 不匹配 | 改 `.env`，**重 build 前端**（见 §8） |
| `docker compose ps` 里 backend 状态 `restarting` | 多半是 `.env` 里 `DATABASE_URL` 密码和 `POSTGRES_PASSWORD` 不一致 | 对齐两个密码；`docker compose down -v` 后重来（**会清库**） |
| `postgres` 启动报 `initdb: directory not empty` | 上次启动残留的 `data/postgres/` 文件 | `docker compose down -v && rm -rf data/postgres && docker compose up -d` |
| GEE 报 `Permission denied` | 服务账号没加到 GEE 项目 | 去 https://code.earthengine.google.com/ 把 `sandbelt-gee@...iam.gserviceaccount.com` 加为 project editor |
| 后端启动卡在 `Loading bge-m3` | 首次下载 HF 模型 | 等 5–15 min，`docker compose logs -f backend` 看进度；之后会缓存到 `data/hf_cache/` |
| 内存 OOM | 4 GB 机器跑 reranker 会炸 | 升配 或 `.env` 里 `RAG_TOP_K_RERANK=3` 降负载 |
| SSE 聊天几秒就断 | 没有反代时不会出现；如果挂 Nginx 要 `proxy_buffering off` + `proxy_read_timeout 300s` | 本文没用 Nginx，忽略 |

---

## 8. 改了 `.env` 后如何应用

不同字段生效方式不同：

| 字段 | 生效方式 |
|---|---|
| `DATABASE_URL` / `REDIS_URL` / `LLM_*` / `GEE_*` / `CORS_ORIGINS` | `docker compose restart backend` |
| `POSTGRES_PASSWORD`（已初始化后改） | 改库里用户密码，**不要重建 pg 卷**：<br>`docker compose exec postgres psql -U sandbelt -d sandbelt_db -c "ALTER USER sandbelt PASSWORD '新密码';"` |
| `NEXT_PUBLIC_API_URL` | **必须重 build**：`docker compose up -d --build frontend` |
| 前端端口 `FRONTEND_PORT` | `docker compose up -d frontend`（`ports` 字段变化需重建） |

---

## 9. 日常运维

```bash
cd /opt/sandbelt/SandbeltOS

# 看状态
docker compose ps
docker stats --no-stream

# 看日志
docker compose logs -f --tail=200 backend
docker compose logs -f --tail=200 frontend

# 重启单个服务
docker compose restart backend

# 停掉全部（保留数据）
docker compose down

# 停掉并清掉所有数据（危险！）
docker compose down -v && rm -rf data/

# 拉新代码后重新部署
git pull          # 或 rsync 新代码上来
docker compose up -d --build
```

### 数据备份

```bash
# 手动备份
mkdir -p /opt/sandbelt/backups
docker compose exec -T postgres pg_dump -U sandbelt -d sandbelt_db -Fc \
  > /opt/sandbelt/backups/sandbelt-$(date +%Y%m%d-%H%M%S).dump

# 自动每天 3 点备份（crontab -e）
0 3 * * * cd /opt/sandbelt/SandbeltOS && docker compose exec -T postgres pg_dump -U sandbelt -d sandbelt_db -Fc > /opt/sandbelt/backups/sandbelt-$(date +\%Y\%m\%d).dump && find /opt/sandbelt/backups -name "*.dump" -mtime +14 -delete
```

---

## 10. 清单：部署结束前自检

- [ ] `docker compose ps` 四个服务全 healthy/running
- [ ] `curl http://localhost:8000/health` 返回 `ok`
- [ ] 浏览器能打开 `http://<SERVER_IP>:3000`
- [ ] `regions` 表有数据
- [ ] `eco_indicators` 表有 > 1000 行（说明 GEE 拉成功）
- [ ] `.env` 里没有 `change-me` / `your-` / `yourpassword` 这些占位符
- [ ] `secrets/gee-key.json` 权限 600
- [ ] 安全组放行 3000 和 8000
- [ ] cron 备份已配

---

*维护：SandbeltOS 团队 · 最后更新：2026-04-20*

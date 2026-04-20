# SandbeltOS · 云服务器部署快速开始

> 最短路径：从 SSH 登录到访问网页。详细说明请看 [`docs/docker.md`](docs/docker.md)。

---

## 你需要准备

**服务器端：**
- 一台 Ubuntu 22.04 的云服务器（阿里云/腾讯云/AWS 等），**4 核 8G 内存以上**
- 能 SSH 登录（`ssh ubuntu@<公网IP>`）
- 云厂商控制台里把 **22 / 80 / 443 / 3000 / 8000** 端口加入安全组

**本地：**
- 项目代码已推到 GitHub（你已完成 ✓）
- `secrets/gee-key.json`（Google Earth Engine 密钥，可选）
- LLM API key（用于 RAG 问答）

---

## 三步部署

### 1. SSH 登录服务器，拉代码

```bash
ssh ubuntu@<你的服务器IP>

sudo mkdir -p /opt/sandbelt && sudo chown $USER:$USER /opt/sandbelt
cd /opt/sandbelt
git clone https://github.com/Jiawang1209/SandbeltOS.git
cd SandbeltOS
```

### 2. 运行一键部署脚本

```bash
bash deploy.sh
```

第一次运行会：装 Docker → 配镜像加速 → 从 `.env.example` 生成 `.env` → 让你去改 `.env`。

### 3. 编辑 .env，再次运行

```bash
vim .env
# 必改这 4 项：
#   POSTGRES_PASSWORD=<openssl rand -base64 24 生成>
#   LLM_API_KEY=<你的 LLM key>
#   NEXT_PUBLIC_API_URL=http://<服务器IP>:8000
#   CORS_ORIGINS=http://<服务器IP>:3000
```

上传 GEE 密钥（如果需要 GEE 功能）：

```bash
# 在本地执行
scp secrets/gee-key.json ubuntu@<服务器IP>:/opt/sandbelt/SandbeltOS/secrets/
```

然后再跑一次部署脚本：

```bash
bash deploy.sh
```

脚本会构建镜像、启动所有容器、等待健康检查通过。**首次约 10–15 分钟**（下载 PyTorch + 前端依赖 + HuggingFace 模型）。

---

## 访问你的应用

```
浏览器：http://<服务器IP>:3000
API 文档：http://<服务器IP>:8000/docs
```

---

## 数据迁移（把本地数据搬到服务器）

启动脚本只让**空应用**跑起来。你本地已有的数据分三类需要迁移：

| 数据 | 本地位置 | 大小 | 必迁吗 |
|---|---|---|---|
| **PostgreSQL 业务数据** | 本机跑的 PostgreSQL | 几十 MB | ✅ 必须 |
| **ChromaDB 向量库** | `backend/rag/chroma_store/` | ~12 MB | ✅ 必须 |
| **RAG 原始 PDF** | `backend/rag/docs/` | ~47 MB | 🟡 可选 |
| **GEE 密钥** | `secrets/gee-key.json` | < 10 KB | ✅ 必须（用 GEE 的话） |

### 选项 A · 用迁移脚本（推荐，一键搞定）

**① 本地导出（在你自己电脑上）：**

```bash
# 先激活 conda 环境和启动本地 PostgreSQL
conda activate sandbelt
pg_ctl -D $CONDA_PREFIX/var/postgresql start

# 运行导出脚本（会在 ./migration/ 生成 dump 和 tgz）
bash scripts/deploy/export_local_data.sh
```

脚本会生成：
```
migration/
├── sandbelt.dump          # 数据库（pg_dump 自定义格式）
├── chroma_store.tgz       # 向量库
├── rag_docs.tgz           # PDF（可选）
└── MANIFEST.txt           # 清单 + 上传命令提示
```

**② 上传到服务器：**

```bash
# 一次传完（替换 <IP>）
scp migration/*.dump migration/*.tgz ubuntu@<服务器IP>:/tmp/

# GEE 密钥（如果有）
scp secrets/gee-key.json ubuntu@<服务器IP>:/opt/sandbelt/SandbeltOS/secrets/
```

**③ 服务器导入：**

```bash
ssh ubuntu@<服务器IP>
cd /opt/sandbelt/SandbeltOS

# 确保容器已经起来
docker compose ps

# 运行导入脚本
bash scripts/deploy/import_to_server.sh
```

脚本会：拷贝 dump 到 postgres 容器 → `pg_restore` 恢复 → 验证记录数 → 停 backend → 替换 ChromaDB → 重启 backend。**整个过程对跑的应用是平滑的**。

### 选项 B · 手动分步（想知道每一步在做什么）

```bash
# --- 本地 ---
pg_dump -U sandbelt -d sandbelt_db -Fc --no-owner --no-privileges -f sandbelt.dump
tar czf chroma.tgz -C backend/rag chroma_store
scp sandbelt.dump chroma.tgz ubuntu@<IP>:/tmp/

# --- 服务器 ---
cd /opt/sandbelt/SandbeltOS

# 恢复数据库
docker compose cp /tmp/sandbelt.dump postgres:/tmp/
docker compose exec postgres pg_restore -U sandbelt -d sandbelt_db \
    --clean --if-exists --no-owner --no-privileges /tmp/sandbelt.dump

# 恢复 ChromaDB（必须先停 backend）
docker compose stop backend
sudo rm -rf data/chroma/*
sudo tar xzf /tmp/chroma.tgz -C data/chroma --strip-components=1
docker compose start backend
```

### 选项 C · 服务器从零开始生成（不带本地数据）

如果你愿意让服务器重新跑一遍数据采集（慢但干净）：

```bash
docker compose exec backend python scripts/seed_region_polygons.py
docker compose exec backend python scripts/seed_accurate_sandy.py
docker compose exec backend python scripts/fetch_real_gee.py  # 需要 GEE 配好
docker compose exec backend python -m rag.ingest              # 需要 PDF 已放在 data/rag_docs/
```

---

### 为什么不能直接 scp PostgreSQL 数据目录？

很多人想 `rsync $CONDA_PREFIX/var/postgresql/` 过去就行。**不行**：
- 本机和服务器 OS 不同（macOS vs Linux），二进制格式有差异
- 服务器里是 TimescaleDB HA 镜像，数据目录布局是 `/home/postgres/pgdata/data`，不是标准位置
- PostgreSQL 锁文件、WAL 日志在跨环境时会冲突

**`pg_dump` → `pg_restore` 是跨平台、跨版本、跨扩展的标准做法**，脚本里已经帮你封装好。

---

## 常用命令

```bash
docker compose ps                     # 看容器状态
docker compose logs -f backend        # 跟后端日志
docker compose logs -f frontend       # 跟前端日志
docker compose restart backend        # 重启单个服务
docker compose down                   # 停所有（数据保留）
docker compose up -d --build          # 代码更新后重新部署
```

---

## 出问题了？

| 症状 | 看这里 |
|------|------|
| 浏览器打不开 `http://IP:3000` | 先检查云厂商安全组是否放通了端口 |
| 前端白屏，F12 看到 CORS 报错 | `.env` 里 `CORS_ORIGINS` 和浏览器地址不一致 |
| 前端 API 全部打到 `localhost:8000` | `NEXT_PUBLIC_API_URL` 改了没重 build：`docker compose build --no-cache frontend` |
| backend 卡在 "Loading bge-m3" | 正常，首次下载 2.5GB 模型，等 5–15 分钟 |
| `docker compose` 报 permission denied | 刚装 Docker，退出 SSH 重连就好 |

更多问题详见 [`docs/docker.md` §11–§12](docs/docker.md)。

---

## 要加 HTTPS / 绑域名？

见 [`docs/docker.md` 附录 A](docs/docker.md)，用 Nginx + Certbot 签 Let's Encrypt 免费证书。

# SandbeltOS 部署总览

> 一页路由文档：根据你的场景挑一条路,然后跳到对应的详细手册。
> 详细步骤都在 [`docs/docker.md`](docker.md);本文不再重复。

---

## 你要走哪条路?

| 场景 | 路径 | 主文档 |
|------|------|--------|
| **本机开发 / 跑测试** | 不部署,直接用 `docker compose up -d` 或 README 「快速开始」 | [`../README.md`](../README.md) §快速开始 |
| **云服务器演示 / IP 直连** | Docker Compose 一键全栈,5 分钟可用 | [`docker.md`](docker.md) §1-9.1 |
| **正式上线 / 域名 + HTTPS** | 同上 + Nginx 反代 + Let's Encrypt | [`docker.md`](docker.md) §9.2 + 附录 A |
| **从零搭一台新服务器** | 装 Docker + 拉代码 + 灌数据(含 GEE service account 步骤) | [`docker.md`](docker.md) §3 + 附录 B |
| **本机已有数据,搬上服务器** | 上面 + `pg_dump` + `chroma_store` tar 迁移 | [`docker.md`](docker.md) §8 |

---

## Docker vs 原生:为什么默认 Docker

| | Docker Compose | 原生 systemd |
|---|---|---|
| 部署时间 | 5-10 min | 1-2 hour |
| 一致性 | ✅ 镜像锁版本 | ⚠️ 系统库差异多 |
| 升级 | `docker compose pull && up -d` | 手动重启每个 service |
| 调试 | `docker compose logs` 一站 | 分散在 journalctl / 容器外 |
| GDAL / TimescaleDB 安装 | 镜像内已就绪 | 自己配 apt 源 |

**结论:** 项目默认走 Docker。如果你坚持要原生 systemd 安装,本仓库 `git log` 里有早期 `docs/deploy-demo.md` 文件(2026-05-19 之前的版本),但**不再维护**——遇到问题不会有人帮你修。

---

## 部署前 checklist

打包带去服务器的东西:

| | 必须 | 备注 |
|---|---|---|
| 项目代码 | ✅ | `git clone` 即可,不需要打 tarball |
| `secrets/gee-key.json` | ✅ | 单独 `scp` 上传,**别 commit** |
| `.env` | ✅ | 在服务器上基于 `.env.example` 现写,密码改强 |
| `data/postgres/` | 可选 | 有本地 dump 就走 §8 迁移,没有就走附录 B 重灌 |
| `data/chroma/` | 可选 | 同上 |
| `data/rag_docs/` (PDF) | 可选 | 有 PDF 才需要;没有可以跳过 RAG |
| `data/hf_cache/` (~2.5GB bge-m3 模型) | 可选 | 不带的话首次启动会从 HuggingFace 下载,慢但能跑 |

**绝对不要带:** `node_modules/` · `.next/` · `__pycache__/` · `*.pyc` · 本机 `venv/` — 这些镜像构建会自动生成。

---

## 出问题去哪儿?

- 容器起不来 → [`docker.md`](docker.md) §12 常见问题排查
- 前端报跨域 / API 连不上 → [`docker.md`](docker.md) §11 关键注意事项 §1 (NEXT_PUBLIC_API_URL 是 build-time 变量)
- DB 数据丢了 → [`docker.md`](docker.md) §10.6 自动备份
- 改了 `.env` 没生效 → [`docker.md`](docker.md) §10.1 更新部署

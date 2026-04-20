#!/usr/bin/env bash
# =========================================================================
# SandbeltOS · 服务器端数据导入脚本
#
# 在云服务器上的项目根目录执行。会从 /tmp/ 读入数据包并恢复到运行中的容器。
#
# 前提：
#   1) 已运行过 bash deploy.sh，容器都起来了
#   2) 本地已经用 scripts/deploy/export_local_data.sh 导出数据
#   3) 用 scp 把 migration/*.dump 和 *.tgz 传到服务器 /tmp/
#
# 用法（服务器上）：
#   cd /opt/sandbelt/SandbeltOS
#   bash scripts/deploy/import_to_server.sh
#
# 环境变量（可选）：
#   DUMP_FILE=/tmp/sandbelt.dump      覆盖默认的 dump 文件路径
#   CHROMA_TGZ=/tmp/chroma_store.tgz
#   PDF_TGZ=/tmp/rag_docs.tgz
#   SKIP_PG=1                         跳过数据库导入
#   SKIP_CHROMA=1                     跳过 ChromaDB 恢复
#   SKIP_PDF=1                        跳过 PDF 解压
# =========================================================================

set -euo pipefail

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'; NC=$'\033[0m'

step()  { echo -e "\n${BLUE}==>${NC} ${1}"; }
ok()    { echo -e "${GREEN}✓${NC} ${1}"; }
warn()  { echo -e "${YELLOW}⚠${NC} ${1}"; }
fatal() { echo -e "${RED}✗${NC} ${1}" >&2; exit 1; }

# ---------- 预检 ----------
[[ -f docker-compose.yml ]] || fatal "请在 SandbeltOS 项目根目录执行"

DUMP_FILE="${DUMP_FILE:-/tmp/sandbelt.dump}"
CHROMA_TGZ="${CHROMA_TGZ:-/tmp/chroma_store.tgz}"
PDF_TGZ="${PDF_TGZ:-/tmp/rag_docs.tgz}"

# 从 .env 读 POSTGRES_USER/DB（默认 sandbelt/sandbelt_db）
PG_USER="sandbelt"
PG_DB="sandbelt_db"
if [[ -f .env ]]; then
  PG_USER=$(grep -E "^POSTGRES_USER=" .env | cut -d= -f2- | tr -d '"' || echo "sandbelt")
  PG_DB=$(grep -E "^POSTGRES_DB=" .env | cut -d= -f2- | tr -d '"' || echo "sandbelt_db")
  PG_USER="${PG_USER:-sandbelt}"
  PG_DB="${PG_DB:-sandbelt_db}"
fi

# 检查容器是否在跑
if ! docker compose ps --services --filter "status=running" 2>/dev/null | grep -q postgres; then
  fatal "postgres 容器未运行。先 'docker compose up -d' 再跑本脚本"
fi

# ---------- 1. PostgreSQL ----------
import_postgres() {
  step "[1/3] 导入 PostgreSQL 数据库"
  if [[ "${SKIP_PG:-0}" == "1" ]]; then
    ok "跳过（SKIP_PG=1）"
    return
  fi
  if [[ ! -f "$DUMP_FILE" ]]; then
    warn "找不到 $DUMP_FILE，跳过数据库导入"
    warn "  如果忘记传了：本地 scp migration/sandbelt.dump <user>@<IP>:/tmp/"
    return
  fi

  echo "   dump 文件：$DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"
  echo "   目标：$PG_USER@postgres:5432/$PG_DB"

  # 拷贝到容器
  echo "   [1/3] 拷贝到 postgres 容器..."
  docker compose cp "$DUMP_FILE" postgres:/tmp/sandbelt.dump

  # 等 postgres 就绪
  for i in {1..30}; do
    if docker compose exec -T postgres pg_isready -U "$PG_USER" -d "$PG_DB" &>/dev/null; then
      break
    fi
    [[ $i -eq 30 ]] && fatal "postgres 30 秒内未就绪"
    sleep 1
  done

  # 恢复（--clean 会先清空旧表，init.sql 建的空表会被覆盖）
  echo "   [2/3] 正在恢复（--clean 会先清理旧数据）..."
  docker compose exec -T postgres pg_restore \
      -U "$PG_USER" -d "$PG_DB" \
      --clean --if-exists \
      --no-owner --no-privileges \
      /tmp/sandbelt.dump 2>&1 | tail -20 || {
    warn "pg_restore 有警告（通常是 --clean 找不到旧对象的告警，可忽略）"
  }

  # 验证
  echo "   [3/3] 验证记录数..."
  docker compose exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -tA <<'SQL' | sed 's/^/     /' 2>/dev/null || true
SELECT 'regions:              ' || count(*) FROM regions UNION ALL
SELECT 'eco_indicators:       ' || count(*) FROM eco_indicators UNION ALL
SELECT 'desertification_risk: ' || count(*) FROM desertification_risk;
SQL
  ok "数据库恢复完成"
}
import_postgres

# ---------- 2. ChromaDB ----------
import_chroma() {
  step "[2/3] 恢复 ChromaDB 向量库"
  if [[ "${SKIP_CHROMA:-0}" == "1" ]]; then
    ok "跳过（SKIP_CHROMA=1）"
    return
  fi
  if [[ ! -f "$CHROMA_TGZ" ]]; then
    warn "找不到 $CHROMA_TGZ，跳过"
    warn "  如果忘记传：本地 scp migration/chroma_store.tgz <user>@<IP>:/tmp/"
    return
  fi

  echo "   包文件：$CHROMA_TGZ ($(du -h "$CHROMA_TGZ" | cut -f1))"

  echo "   [1/3] 停 backend..."
  docker compose stop backend

  echo "   [2/3] 清空旧向量库并解压..."
  mkdir -p data/chroma
  sudo rm -rf data/chroma/* 2>/dev/null || rm -rf data/chroma/*
  # tar 内部结构是 chroma_store/..., 用 --strip-components=1 去掉顶层目录
  sudo tar xzf "$CHROMA_TGZ" -C data/chroma --strip-components=1 2>/dev/null || \
       tar xzf "$CHROMA_TGZ" -C data/chroma --strip-components=1
  sudo chown -R 0:0 data/chroma 2>/dev/null || true

  echo "   [3/3] 重启 backend..."
  docker compose start backend
  ok "ChromaDB 恢复完成"
  echo "   用 'docker compose logs -f backend' 确认没有 chroma 加载错误"
}
import_chroma

# ---------- 3. RAG PDFs（可选） ----------
import_pdfs() {
  step "[3/3] 解压 RAG 原始 PDF（可选）"
  if [[ "${SKIP_PDF:-0}" == "1" ]]; then
    ok "跳过（SKIP_PDF=1）"
    return
  fi
  if [[ ! -f "$PDF_TGZ" ]]; then
    warn "找不到 $PDF_TGZ，跳过（仅用于以后重新 ingest 时需要）"
    return
  fi

  echo "   包文件：$PDF_TGZ ($(du -h "$PDF_TGZ" | cut -f1))"
  mkdir -p data/rag_docs
  sudo tar xzf "$PDF_TGZ" -C data/rag_docs --strip-components=1 2>/dev/null || \
       tar xzf "$PDF_TGZ" -C data/rag_docs --strip-components=1
  ok "PDF 解压完成到 data/rag_docs/"
}
import_pdfs

# ---------- 总结 ----------
step "迁移完成"
cat <<EOF

  ${GREEN}下一步验证：${NC}
    # 1) 健康检查
    curl http://localhost:8000/health

    # 2) 查看数据库几个核心表
    docker compose exec postgres psql -U $PG_USER -d $PG_DB \\
        -c "SELECT count(*) FROM eco_indicators;"

    # 3) 浏览器打开前端，看地图和指标是否有数据
    echo "http://\$(curl -s ifconfig.me):3000"

  ${YELLOW}如果有问题：${NC}
    docker compose logs -f backend         # 看后端日志
    docker compose logs --tail=50 postgres # 看数据库日志

EOF

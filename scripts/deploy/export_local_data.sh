#!/usr/bin/env bash
# =========================================================================
# SandbeltOS · 本地数据导出脚本
#
# 在你本地机器的项目根目录执行。会把需要迁移到服务器的数据打包到 ./migration/
#
# 产物：
#   migration/sandbelt.dump           —— PostgreSQL 业务数据（pg_dump）
#   migration/chroma_store.tgz        —— ChromaDB 向量库
#   migration/rag_docs.tgz            —— RAG 原始 PDF（可选）
#   migration/MANIFEST.txt            —— 导出清单和上传命令提示
#
# 用法：
#   cd /path/to/SandbeltOS
#   bash scripts/deploy/export_local_data.sh
#
# 环境变量（可选覆盖默认值）：
#   PG_USER=sandbelt            数据库用户名
#   PG_DB=sandbelt_db           数据库名
#   PG_HOST=localhost           数据库主机
#   PG_PORT=5432                数据库端口
#   SKIP_PG=1                   跳过数据库导出
#   SKIP_CHROMA=1               跳过 ChromaDB 导出
#   SKIP_PDF=1                  跳过 RAG PDF 导出
# =========================================================================

set -euo pipefail

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'; NC=$'\033[0m'

step()  { echo -e "\n${BLUE}==>${NC} ${1}"; }
ok()    { echo -e "${GREEN}✓${NC} ${1}"; }
warn()  { echo -e "${YELLOW}⚠${NC} ${1}"; }
fatal() { echo -e "${RED}✗${NC} ${1}" >&2; exit 1; }

# ---------- 预检 ----------
[[ -f .env ]] || warn "当前目录没有 .env（导出仍可继续，但建议确认在项目根）"
[[ -d backend/rag ]] || fatal "请在 SandbeltOS 项目根目录执行（找不到 backend/rag）"

PG_USER="${PG_USER:-sandbelt}"
PG_DB="${PG_DB:-sandbelt_db}"
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"

OUTDIR="migration"
mkdir -p "$OUTDIR"
TS=$(date +%Y%m%d-%H%M%S)

# ---------- 1. PostgreSQL ----------
export_postgres() {
  step "[1/3] 导出 PostgreSQL 数据库"
  if [[ "${SKIP_PG:-0}" == "1" ]]; then
    ok "跳过（SKIP_PG=1）"
    return
  fi
  if ! command -v pg_dump &>/dev/null; then
    warn "找不到 pg_dump 命令。如果你用 conda，先 'conda activate sandbelt'"
    warn "或者 SKIP_PG=1 bash $0 跳过这一步"
    return 1
  fi

  echo "   连接：$PG_USER@$PG_HOST:$PG_PORT/$PG_DB"
  if ! pg_isready -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" &>/dev/null; then
    warn "PostgreSQL 连不上（$PG_HOST:$PG_PORT）。本地数据库是否启动？"
    warn "  conda activate sandbelt && pg_ctl -D \$CONDA_PREFIX/var/postgresql start"
    return 1
  fi

  DUMP="$OUTDIR/sandbelt.dump"
  echo "   正在 pg_dump（自定义格式，支持并行恢复）..."
  pg_dump -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
          -Fc --no-owner --no-privileges \
          -f "$DUMP"
  SIZE=$(du -h "$DUMP" | cut -f1)
  ok "导出成功：$DUMP ($SIZE)"

  # 简单 sanity check：统计几个核心表
  echo "   核心表记录数（供参考）："
  psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -tA <<'SQL' 2>/dev/null | sed 's/^/     /' || true
SELECT 'regions:           ' || count(*) FROM regions UNION ALL
SELECT 'eco_indicators:    ' || count(*) FROM eco_indicators UNION ALL
SELECT 'desertification_risk: ' || count(*) FROM desertification_risk;
SQL
}
export_postgres || warn "数据库导出失败，但可继续其他步骤"

# ---------- 2. ChromaDB ----------
export_chroma() {
  step "[2/3] 导出 ChromaDB 向量库"
  if [[ "${SKIP_CHROMA:-0}" == "1" ]]; then
    ok "跳过（SKIP_CHROMA=1）"
    return
  fi
  if [[ ! -d backend/rag/chroma_store ]] || [[ -z "$(ls -A backend/rag/chroma_store 2>/dev/null)" ]]; then
    warn "backend/rag/chroma_store 不存在或为空 —— 你还没 ingest 过 RAG 语料？"
    warn "如果打算在服务器上重新 ingest，可以忽略"
    return
  fi
  OUT="$OUTDIR/chroma_store.tgz"
  echo "   正在打包 backend/rag/chroma_store ..."
  tar czf "$OUT" -C backend/rag chroma_store
  SIZE=$(du -h "$OUT" | cut -f1)
  ok "打包成功：$OUT ($SIZE)"
}
export_chroma

# ---------- 3. RAG PDFs（可选） ----------
export_pdfs() {
  step "[3/3] 导出 RAG 原始 PDF（可选）"
  if [[ "${SKIP_PDF:-0}" == "1" ]]; then
    ok "跳过（SKIP_PDF=1）"
    return
  fi
  if [[ ! -d backend/rag/docs ]] || [[ -z "$(ls -A backend/rag/docs 2>/dev/null)" ]]; then
    warn "backend/rag/docs 不存在或为空，跳过"
    return
  fi
  OUT="$OUTDIR/rag_docs.tgz"
  echo "   正在打包 backend/rag/docs（排除日志）..."
  tar czf "$OUT" \
      --exclude='*.log' \
      --exclude='manifest*.json' \
      -C backend/rag docs
  SIZE=$(du -h "$OUT" | cut -f1)
  ok "打包成功：$OUT ($SIZE)"
  echo "   提示：PDF 在服务器端只有重新跑 ingest 才用得到；"
  echo "         如果你带了 chroma_store.tgz，这份 PDF 可以不传。"
}
export_pdfs

# ---------- 清单 & 上传提示 ----------
step "生成上传清单"
MANIFEST="$OUTDIR/MANIFEST.txt"
{
  echo "SandbeltOS · 数据导出清单 ($TS)"
  echo "================================"
  echo ""
  echo "文件大小："
  ls -lh "$OUTDIR"/ 2>/dev/null | tail -n +2 | awk '{print "  " $9 ": " $5}'
  echo ""
  echo "一键上传命令（替换 <用户名> 和 <服务器IP>）："
  echo ""
  echo "  scp $OUTDIR/*.dump $OUTDIR/*.tgz <用户名>@<服务器IP>:/tmp/"
  echo ""
  echo "  # 然后 SSH 到服务器："
  echo "  ssh <用户名>@<服务器IP>"
  echo "  cd /opt/sandbelt/SandbeltOS"
  echo "  bash scripts/deploy/import_to_server.sh"
} | tee "$MANIFEST"

echo ""
ok "全部完成！产物在 ./$OUTDIR/"
echo ""
warn "⚠️ 不要把 migration/ 目录提交到 Git（.gitignore 需要排除，下面会处理）"

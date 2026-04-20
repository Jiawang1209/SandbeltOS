#!/usr/bin/env bash
# =========================================================================
# SandbeltOS · 一键部署脚本
#
# 功能：
#   1) 检测并安装 Docker + Docker Compose（Ubuntu/Debian）
#   2) 配置国内镜像加速（可选）
#   3) 创建 .env（从 .env.example）并强制校验关键字段
#   4) 建立持久化挂载目录并设好权限
#   5) 检查 secrets/gee-key.json 权限（可选）
#   6) docker compose up -d --build
#   7) 等待服务健康并自检
#
# 用法：
#   # 1) 登录服务器，拉代码
#   git clone https://github.com/Jiawang1209/SandbeltOS.git /opt/sandbelt/SandbeltOS
#   cd /opt/sandbelt/SandbeltOS
#
#   # 2) 运行本脚本（第一次需要 sudo 装 Docker）
#   bash deploy.sh
#
#   # 3) 根据提示编辑 .env，再次运行即可启动
#   bash deploy.sh
#
# 环境变量（可选）：
#   SKIP_DOCKER_INSTALL=1   已装过 Docker 时跳过安装步骤
#   SKIP_MIRROR=1           不配置国内镜像
#   SKIP_SECRETS=1          不要 GEE 密钥（例如仅跑前端后端，不调 GEE）
#   FORCE_REBUILD=1         构建时加 --no-cache
# =========================================================================

set -euo pipefail

# ---------- 颜色 ----------
RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'; NC=$'\033[0m'

step()  { echo -e "\n${BLUE}==>${NC} ${1}"; }
ok()    { echo -e "${GREEN}✓${NC} ${1}"; }
warn()  { echo -e "${YELLOW}⚠${NC} ${1}"; }
err()   { echo -e "${RED}✗${NC} ${1}" >&2; }
fatal() { err "$1"; exit 1; }

# ---------- 预检 ----------
[[ -f docker-compose.yml ]] || fatal "请在项目根目录运行（应能看到 docker-compose.yml）"
[[ -f .env.example ]]       || fatal ".env.example 缺失，项目不完整？"

step "检查操作系统"
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  echo "   发行版：$PRETTY_NAME"
  case "$ID" in
    ubuntu|debian) ok "支持的发行版" ;;
    *) warn "非 Ubuntu/Debian，脚本的 Docker 安装步骤可能不适用，请手动安装后再跑本脚本（SKIP_DOCKER_INSTALL=1）" ;;
  esac
else
  warn "无法识别发行版"
fi

# ---------- 1. Docker ----------
install_docker() {
  step "安装 Docker 和 Docker Compose"
  if [[ "${SKIP_DOCKER_INSTALL:-0}" == "1" ]]; then
    ok "跳过 Docker 安装（SKIP_DOCKER_INSTALL=1）"
    return
  fi

  if command -v docker &>/dev/null && docker compose version &>/dev/null; then
    ok "Docker 已安装：$(docker --version)"
    ok "Compose 已安装：$(docker compose version)"
    return
  fi

  echo "   使用官方一键脚本安装..."
  if curl -fsSL https://get.docker.com 2>/dev/null | sudo sh; then
    ok "Docker 安装成功"
  else
    err "官方脚本安装失败，请参考 docs/docker.md §3 方式 B 手动安装"
    exit 1
  fi

  sudo systemctl enable --now docker
  sudo groupadd docker 2>/dev/null || true
  sudo usermod -aG docker "$USER"
  warn "已把 $USER 加入 docker 组，你需要 **退出 SSH 重新登录** 才能免 sudo 用 docker"
  warn "或者在当前 shell 执行：newgrp docker"
}
install_docker

# ---------- 2. 国内镜像加速（可选） ----------
configure_mirror() {
  step "配置 Docker 镜像加速"
  if [[ "${SKIP_MIRROR:-0}" == "1" ]]; then
    ok "跳过镜像加速（SKIP_MIRROR=1）"
    return
  fi
  if [[ -f /etc/docker/daemon.json ]] && grep -q "registry-mirrors" /etc/docker/daemon.json 2>/dev/null; then
    ok "已存在镜像加速配置，跳过"
    return
  fi
  sudo tee /etc/docker/daemon.json >/dev/null <<'JSON'
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "5"
  }
}
JSON
  sudo systemctl restart docker
  ok "已写入 /etc/docker/daemon.json 并重启 Docker"
}
configure_mirror

# ---------- 3. .env ----------
step "检查 .env 文件"
if [[ ! -f .env ]]; then
  cp .env.example .env
  warn "已从 .env.example 生成 .env。请编辑以下关键字段后再次运行本脚本："
  cat <<EOF

  必改：
    POSTGRES_PASSWORD       —— 强密码（openssl rand -base64 24 生成一个）
    LLM_API_KEY             —— 你的 LLM API key
    NEXT_PUBLIC_API_URL     —— 生产前端打到哪个后端地址
                               IP 模式：http://<服务器IP>:8000
                               同域反代：https://yourdomain.com
    CORS_ORIGINS            —— 浏览器访问地址（必须和上面匹配）
                               IP 模式：http://<服务器IP>:3000
                               同域反代：https://yourdomain.com

  可选：
    CDS_KEY / OPENAI_API_KEY / GEE_SERVICE_ACCOUNT / GEE_PROJECT
    HF_ENDPOINT=https://hf-mirror.com   （国内服务器加速 HuggingFace）

  编辑好后：
    vim .env
    bash deploy.sh

EOF
  exit 0
fi

# 校验：POSTGRES_PASSWORD 不能是默认值
if grep -q "^POSTGRES_PASSWORD=change-me-to-a-strong-password" .env; then
  fatal ".env 里 POSTGRES_PASSWORD 还是默认值 change-me-to-a-strong-password，请改成强密码"
fi
if grep -q "^POSTGRES_PASSWORD=$" .env || ! grep -q "^POSTGRES_PASSWORD=" .env; then
  fatal ".env 里 POSTGRES_PASSWORD 为空，请填入强密码（openssl rand -base64 24）"
fi
if grep -q "^LLM_API_KEY=your-uni-api-key" .env; then
  warn "LLM_API_KEY 还是示例值，RAG 问答功能将不可用（不影响其他部分启动）"
fi
if grep -q "^NEXT_PUBLIC_API_URL=http://localhost:8000" .env; then
  warn "NEXT_PUBLIC_API_URL 还是 localhost，浏览器将无法访问 API。"
  warn "   如果只是本地测试可忽略；生产请改为 http://<服务器IP>:8000 或你的域名"
fi
ok ".env 校验通过"

# ---------- 4. 挂载目录 ----------
step "创建持久化挂载目录"
mkdir -p secrets \
         data/postgres \
         data/redis \
         data/chroma \
         data/rag_docs \
         data/hf_cache
ok "已创建 data/ 和 secrets/"

# ---------- 5. GEE 密钥 ----------
step "检查 GEE 密钥"
if [[ "${SKIP_SECRETS:-0}" == "1" ]]; then
  ok "跳过 GEE 密钥检查（SKIP_SECRETS=1）"
elif [[ -f secrets/gee-key.json ]]; then
  chmod 600 secrets/gee-key.json
  ok "secrets/gee-key.json 存在并已设为 600"
else
  warn "secrets/gee-key.json 不存在"
  warn "   如果你要用 Google Earth Engine 功能，请从本地上传："
  warn "     scp secrets/gee-key.json <user>@<IP>:$(pwd)/secrets/"
  warn "   不用 GEE 的话可忽略（backend 启动后调 GEE 接口会报错，但不影响其他功能）"
fi

# ---------- 6. 构建 & 启动 ----------
step "构建并启动所有服务"
BUILD_ARGS=""
[[ "${FORCE_REBUILD:-0}" == "1" ]] && BUILD_ARGS="--no-cache"

if ! docker info &>/dev/null; then
  fatal "docker 命令无权限。如果刚装完 Docker，请 'exit' 重连 SSH 后再试（或执行 newgrp docker）"
fi

echo "   （首次构建约 10–15 分钟，下载 PyTorch 和前端依赖）"
docker compose build $BUILD_ARGS
docker compose up -d
ok "容器已启动"

# ---------- 7. 等待健康 ----------
step "等待服务就绪"
for i in {1..60}; do
  if docker compose ps --format json 2>/dev/null | grep -q '"State":"running"'; then
    sleep 1
  fi
  if curl -sf http://localhost:8000/health &>/dev/null; then
    ok "后端 http://localhost:8000/health 就绪"
    break
  fi
  [[ $i -eq 60 ]] && warn "后端 60 秒内未就绪，可能还在下载模型。用 'docker compose logs -f backend' 看日志"
  sleep 2
done

# 前端简单自检
if curl -sI http://localhost:3000 2>/dev/null | grep -qE "^HTTP/1.[01] (200|307|308)"; then
  ok "前端 http://localhost:3000 就绪"
else
  warn "前端暂未就绪，用 'docker compose logs -f frontend' 看日志"
fi

# ---------- 8. 总结 ----------
step "部署完成"
PUBLIC_IP=$(curl -sf --max-time 3 ifconfig.me 2>/dev/null || echo "<服务器公网IP>")
cat <<EOF

  ${GREEN}容器状态：${NC}
$(docker compose ps)

  ${GREEN}访问地址：${NC}
    前端：http://${PUBLIC_IP}:3000
    后端：http://${PUBLIC_IP}:8000/docs        （Swagger UI）
    健康：http://${PUBLIC_IP}:8000/health

  ${GREEN}下一步（数据初始化）：${NC}
    # 若有本地数据要迁移，见 docs/docker.md §8
    # 若从零开始，用种子脚本：
    docker compose exec backend python scripts/seed_region_polygons.py
    docker compose exec backend python -m rag.ingest   # RAG 向量化

  ${GREEN}常用命令：${NC}
    docker compose logs -f backend       # 跟后端日志
    docker compose restart backend       # 重启后端
    docker compose down                  # 停掉所有服务（保留数据）

  ${YELLOW}提醒：${NC}
  - 云厂商安全组要放通 22/80/443/3000/8000，否则外网访问不到
  - NEXT_PUBLIC_API_URL 改动后必须 'docker compose build --no-cache frontend'
  - 首次 backend 启动会下载 bge-m3 模型（~2.5GB），正常 5-10 分钟

EOF

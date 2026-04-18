# syntax=docker/dockerfile:1.7

# =========================================================================
# SandbeltOS Frontend (Next.js 16 + React 19)
# 关键：NEXT_PUBLIC_API_URL 必须在 `npm run build` 前注入，否则线上会打到
# http://localhost:8000（浏览器端会 404）。通过 --build-arg 传进来。
# =========================================================================

# ---------- builder ----------
FROM node:20-bookworm-slim AS builder

WORKDIR /app

# 先只拷 package.json 以最大化 Docker 层缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./

# 构建期注入 API 基址（NEXT_PUBLIC_* 会被 Next.js inline 到前端 bundle）
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

# ---------- runner ----------
FROM node:20-bookworm-slim AS runner

WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# 仅复制运行需要的文件
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.ts ./next.config.ts

EXPOSE 3000

CMD ["npm", "run", "start"]

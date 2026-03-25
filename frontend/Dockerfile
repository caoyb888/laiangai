FROM node:20-alpine AS base

# 安装 pnpm（见 CLAUDE.md §2.1，禁止使用 npm/yarn）
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# 安装依赖（分层缓存）
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# ── 开发阶段（Vite dev server）─────────────────────────────
FROM base AS dev
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

# ── 构建阶段 ────────────────────────────────────────────────
FROM base AS build
COPY . .
RUN pnpm build

# ── 生产阶段（Nginx 静态服务）───────────────────────────────
FROM nginx:1.25-alpine AS production

# 拷贝构建产物
COPY --from=build /app/dist /usr/share/nginx/html

# 单页应用路由：所有路径回落到 index.html
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # 静态资源长缓存
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

EXPOSE 80

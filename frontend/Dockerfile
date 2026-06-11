# ─── Stage 1: build ──────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Установка по package-lock.json (npm ci падает на optional peer-deps
# из дерева Nuxt 4 — известный баг npm, поэтому npm install)
COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund

COPY . .
RUN npm run build

# ─── Stage 2: runtime ────────────────────────────────────────────────
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NUXT_HOST=0.0.0.0
ENV NUXT_PORT=3000

COPY --from=builder /app/.output ./output

EXPOSE 3000

CMD ["node", "output/server/index.mjs"]

# Pinned: 2026-03-23
FROM node:20-alpine@sha256:5bac2112f1a27db4775ce6ead86db9e0cbc087f0dbddfe3cbc11ecea122d5294 AS base

WORKDIR /app
ARG NPM_VERSION=11.12.1

RUN apk upgrade --no-cache \
    && npm install -g "npm@${NPM_VERSION}"

FROM base AS deps
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps || npm install --legacy-peer-deps

FROM base AS builder
ARG NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
ARG BACKEND_URL=http://localhost:8000
ENV NEXT_PUBLIC_BACKEND_URL=$NEXT_PUBLIC_BACKEND_URL
ENV BACKEND_URL=$BACKEND_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN mkdir -p public
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine@sha256:5bac2112f1a27db4775ce6ead86db9e0cbc087f0dbddfe3cbc11ecea122d5294 AS runner
WORKDIR /app

RUN apk upgrade --no-cache \
    && rm -rf /usr/local/lib/node_modules/npm \
    && rm -f /usr/local/bin/npm /usr/local/bin/npx

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]

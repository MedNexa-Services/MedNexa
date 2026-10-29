# Multi-stage Dockerfile for MedNexa Admin Dashboard
FROM node:20-alpine AS base
WORKDIR /app

# Install dependencies
FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci

# Build the Next.js application
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
# NEXT_PUBLIC_* values are baked into the browser bundle at build time: pass the
# backend URL as the browser will reach it, e.g.
#   docker build --build-arg NEXT_PUBLIC_API_URL=https://hospital.example/api/v1 .
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# Production runner image
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Add non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

USER nextjs

# Runtime configuration (never baked into the image): AUTH_SECRET, STAFF_EMAIL,
# STAFF_PASSWORD, optionally STAFF_NAME and AUTH_COOKIE_SECURE. See .env.example.
EXPOSE 3000

CMD ["npm", "start"]

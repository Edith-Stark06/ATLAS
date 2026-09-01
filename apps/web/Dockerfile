# syntax=docker/dockerfile:1
#
# Built from the repository root, not from apps/web — this is a monorepo with
# hoisted dependencies, and a build context rooted at the app would be missing
# the root node_modules and lockfile.
#
#   docker build -f apps/web/Dockerfile .

# ---- dependencies -----------------------------------------------------------
FROM node:22-alpine AS deps

WORKDIR /repo

# Manifests only, so this layer survives source edits.
COPY package.json package-lock.json* ./
COPY apps/web/package.json ./apps/web/

RUN npm ci --ignore-scripts

# ---- build ------------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /repo

# Only one workspace exists (apps/web), so npm ci hoists every dependency
# into the root node_modules and never creates a per-workspace one — Node's
# module resolution walks up from apps/web to find it there regardless. An
# earlier version of this Dockerfile also copied apps/web/node_modules,
# which doesn't exist after a clean `npm ci` and made every build of this
# image fail before it ever produced a runnable one.
COPY --from=deps /repo/node_modules ./node_modules
COPY . .

# Baked in at build time: NEXT_PUBLIC_* values are inlined into the client
# bundle, so they cannot be supplied at runtime like ordinary env vars.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build --workspace apps/web

# ---- runtime ----------------------------------------------------------------
FROM node:22-alpine AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

WORKDIR /app

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# The standalone output already contains the trimmed node_modules it needs.
COPY --from=build --chown=nextjs:nodejs /repo/apps/web/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=nextjs:nodejs /repo/apps/web/public ./apps/web/public

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD node -e "require('http').get('http://localhost:3000/', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

# Path mirrors the monorepo layout inside the standalone bundle.
CMD ["node", "apps/web/server.js"]

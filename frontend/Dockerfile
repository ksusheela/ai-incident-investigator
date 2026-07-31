FROM node:24-alpine AS base

WORKDIR /app

# Install dependencies first so they're cached independently of source changes.
COPY package.json package-lock.json ./
RUN npm ci

# --- development ---
# Runs the Vite dev server with HMR. docker-compose.yml bind-mounts src/,
# tests/, public/, and index.html over this so edits on the host take
# effect immediately. VITE_API_BASE_URL is read at container start (not
# baked in) since `vite dev`, unlike `vite build`, re-reads env at runtime.
FROM base AS development

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# --- build (production bundle) ---
FROM base AS build

# Baked into the static bundle at build time — Vite only exposes VITE_*
# vars this way, there is no runtime env for a static SPA.
ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY . .
RUN npm run build

# --- production ---
# Static bundle served by nginx, with SPA fallback for client-side routes.
FROM nginx:1.27-alpine AS production

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=10s \
    CMD wget -qO- http://localhost:8080/health || exit 1

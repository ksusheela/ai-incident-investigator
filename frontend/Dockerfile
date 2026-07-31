# --- Build stage ---
FROM node:24-alpine AS build

WORKDIR /app

# Install dependencies first so they're cached independently of source changes.
COPY package.json package-lock.json ./
RUN npm ci

# Baked into the static bundle at build time — Vite only exposes VITE_*
# vars this way, there is no runtime env for a static SPA.
ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY . .
RUN npm run build

# --- Serve stage ---
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=10s \
    CMD wget -qO- http://localhost:8080/health || exit 1

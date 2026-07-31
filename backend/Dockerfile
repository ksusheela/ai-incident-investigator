FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Install dependencies first so they're cached independently of app code changes.
COPY pyproject.toml uv.lock ./

# --- development ---
# Includes dev-group deps (pytest, ruff) and runs uvicorn with --reload.
# docker-compose.yml bind-mounts src/, tests/, and alembic.ini over this so
# edits on the host take effect without a rebuild.
FROM base AS development

RUN uv sync --frozen --no-install-project
COPY . .
RUN uv sync --frozen \
    && useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --- production ---
# No dev dependencies, no reload, source baked into the image (no mounts).
FROM base AS production

RUN uv sync --frozen --no-install-project --no-dev
COPY src ./src
COPY alembic.ini ./
RUN uv sync --frozen --no-dev \
    && useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]

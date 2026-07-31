# Feature 1: Backend Foundation

## What was built

The backend's structural foundation — the base every later feature (log upload, agents, evaluation, ...) builds on:

- FastAPI application factory (`backend/src/app/main.py`) with a `lifespan` context manager for startup/shutdown logging
- Environment-driven configuration via `pydantic-settings` (`backend/src/app/config.py`, `backend/.env.example`)
- Structured stdout logging (`backend/src/app/logging_config.py`)
- Async SQLAlchemy 2.0 + SQLite (via `aiosqlite`) engine, session factory, and a `get_db_session()` FastAPI dependency (`backend/src/app/database.py`)
- `GET /api/v1/health` — reports app status and verifies real DB connectivity by executing `SELECT 1` (`backend/src/app/api/health.py`)
- Async test suite (`pytest` + `pytest-asyncio` + `httpx.AsyncClient`) exercising the health endpoint against an isolated temp SQLite DB per test run
- `backend/Dockerfile` (slim, non-root, `uv`-based) and root `docker-compose.yml` (backend service + named volume for the SQLite file)
- `ruff` configured for linting (`backend/pyproject.toml`)

See `ARCHITECTURE.md` for the reasoning behind these choices, including why `domain/`/`infrastructure/` layers are deliberately not created yet.

## How to run it

**Locally (uv):**
```bash
cd backend
uv sync
uv run uvicorn app.main:app --app-dir src --reload
curl http://localhost:8000/api/v1/health
```

**Via Docker Compose (from repo root):**
```bash
docker compose up --build
curl http://localhost:8000/api/v1/health
```

## How to test it

```bash
cd backend
uv run pytest -v
uv run ruff check .
```

## Verification performed

- `uv sync` — clean install
- `uv run pytest -v` — 1/1 passing (`test_health_returns_ok_and_confirms_db_connection`)
- `uv run ruff check .` — no errors
- `uv run uvicorn ...` + `curl /api/v1/health` — returned `{"status":"ok","db_connected":true,...}`
- `docker compose up --build` — image built, container reported `healthy`, `curl /api/v1/health` against the containerized service returned the same successful response

## Decisions worth calling out

- **No `domain/`/`infrastructure/` folders yet** — there's no business logic to house there until Feature 2 introduces real entities (e.g. `LogFile`). See `ARCHITECTURE.md`.
- **DI via FastAPI `Depends()`**, not a separate DI framework — idiomatic at this scale, and what the rest of the app will consistently use.
- **SQLite chosen for the MVP**, accessed through the same async-session shape a future Postgres migration would use.

## What's next

Feature 2: log upload & storage — the first real domain entities and repositories.

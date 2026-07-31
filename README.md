# AI Incident Investigator

An AI-powered incident investigation platform: upload application logs, detect production incidents, get automated root-cause analysis and fix suggestions, and generate incident reports — built on a multi-agent architecture (LangGraph orchestration, Claude/Gemini, MCP integration, guardrails, and evaluation).

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for design decisions and [`docs/features/`](docs/features/) for a log of what's been built, feature by feature. Contributor/agent rules live in [`PROJECT_RULES.md`](PROJECT_RULES.md).

## Status

Backend foundation is in place: FastAPI + async SQLAlchemy/SQLite, Alembic migrations, OpenAPI docs, structured logging, and Docker. The frontend (React + TypeScript + Bootstrap 5, responsive sidebar layout, Dashboard/Incidents/Reports/Settings pages) is also built, ahead of its original roadmap slot. See [`docs/features/`](docs/features/) for the full build log. The remaining target folder structure (agents, domain, MCP, guardrails, evaluation) is scaffolded but not yet implemented — see `ARCHITECTURE.md` for what's real vs. planned, including which frontend pages call backend endpoints that don't exist yet and why that's intentional rather than a bug.

## Project layout

```text
backend/     FastAPI backend (Python 3.12, uv-managed)
frontend/    React + TypeScript + Bootstrap 5 client (Vite)
docs/        Per-feature documentation, ADRs, API reference, runbooks
scripts/     Dev/ops helper scripts
```

See `ARCHITECTURE.md` → "Full project layout" for the complete folder-by-folder breakdown.

## Quickstart

### Backend — local (uv)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync
uv run uvicorn app.main:app --app-dir src --reload
```

The API is served at `http://localhost:8000`:

- Health check: `GET /api/v1/health`
- Interactive docs: `/docs` (Swagger) and `/redoc` — disabled automatically when `APP_ENV=production`

### Backend — Docker Compose

```bash
docker compose up --build
```

Serves the same API at `http://localhost:8000`.

### Database migrations (Alembic)

```bash
cd backend
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```

Or against the container: `docker compose exec backend uv run alembic upgrade head`.

### Tests & linting

```bash
cd backend
uv run pytest -v
uv run ruff check .
```

### Frontend — local (npm)

Requires Node.js.

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Served at `http://localhost:5173`. Run the backend alongside it (above) to see live data instead of "unreachable"/"not available yet" states.

### Frontend — Docker Compose

```bash
docker compose up --build
```

Runs both services together: frontend at `http://localhost:5173`, backend at `http://localhost:8000`.

### Frontend tests & linting

```bash
cd frontend
npm run lint
npx tsc -b
npm run test
npm run build
```

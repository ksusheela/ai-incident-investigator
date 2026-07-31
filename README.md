# AI Incident Investigator

An AI-powered incident investigation platform: upload application logs, detect production incidents, get automated root-cause analysis and fix suggestions, and generate incident reports — built on a multi-agent architecture (LangGraph orchestration, Claude/Gemini, MCP integration, guardrails, and evaluation).

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for design decisions and [`docs/features/`](docs/features/) for a log of what's been built, feature by feature. Contributor/agent rules live in [`PROJECT_RULES.md`](PROJECT_RULES.md).

## Status

Backend foundation is in place: FastAPI + async SQLAlchemy/SQLite, Alembic migrations, OpenAPI docs, structured logging, and Docker. The frontend (React + TypeScript + Bootstrap 5, responsive sidebar layout, Dashboard/Incidents/Reports/Settings pages) is also built, ahead of its original roadmap slot. Both services are containerized with separate **development** (hot reload) and **production** (built artifacts) Compose configs. A **LangGraph multi-agent orchestrator** (`POST /api/v1/investigations`, plus `POST /api/v1/investigations/upload` for log files) analyzes logs through five agents — Monitoring, Log Analysis, Root Cause, Recommendation, Report — with Claude/Gemini swappable behind one provider interface (see `ARCHITECTURE.md` → "Multi-agent orchestration"). **Monitoring and Log Analysis are both rule-based** (regex-driven error/warning detection, severity scoring, stack-trace extraction, repeated-failure grouping, and anomaly detection — no LLM call) and need no API key at all; the three agents after them do, and only run if Monitoring actually finds an incident — logs with no errors get a full, real response with zero LLM calls. Running the deeper analysis requires an `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` (see below); without one, those requests fail fast with a clear `503` rather than an obscure error. Root Cause matches evidence against a small curated catalog of known failure patterns and produces a numeric, bounded `confidence_score` plus explicit `reasoning` — not a loose "high/medium/low" string. Recommendation groups fixes into `code_fixes`/`configuration_changes`/`database_improvements`, each with its own `rationale`, rather than a generic action list. Report assembles a professional six-section Markdown document (Summary, Root Cause, Evidence, Confidence, Recommendation, Next Steps) deterministically from the earlier agents' validated data, with only the Summary and Next Steps LLM-authored — and it can be exported as a downloadable `.md` file via `/investigations/export` or `/investigations/upload/export`. See [`docs/features/`](docs/features/) for the full build log. The remaining target folder structure (domain persistence, MCP, guardrails, evaluation) is scaffolded but not yet implemented — see `ARCHITECTURE.md` for what's real vs. planned, including which frontend pages call backend endpoints that don't exist yet and why that's intentional rather than a bug.

## Project layout

```text
backend/     FastAPI backend (Python 3.12, uv-managed)
frontend/    React + TypeScript + Bootstrap 5 client (Vite)
docs/        Per-feature documentation, ADRs, API reference, runbooks
scripts/     Dev/ops helper scripts
```

See `ARCHITECTURE.md` → "Full project layout" for the complete folder-by-folder breakdown.

## Quickstart

### Docker Compose (both services, dev or prod)

**Development** (default — hot reload for both services):

```bash
docker compose up --build
```

**Production** (built artifacts — static frontend bundle via nginx, backend without reload/docs):

```bash
docker compose -f docker-compose.prod.yml up --build
```

Either way: backend at `http://localhost:8000`, frontend at `http://localhost:5173`. See `ARCHITECTURE.md` → "Containerization" for what differs between the two and why they're separate files.

### Backend — local (uv)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync
uv run uvicorn app.main:app --app-dir src --reload
```

The API is served at `http://localhost:8000`:

- Health check: `GET /api/v1/health`
- Investigation pipeline: `POST /api/v1/investigations` with `{"logs": "..."}`, or `POST /api/v1/investigations/upload` with a log file — logs with no errors return a full result with no LLM call needed; logs with errors need `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` set in `backend/.env` (copy from `.env.example`) to proceed past Log Analysis (also rule-based, also free) to Root Cause
- Export the final report as a `.md` file: `POST /api/v1/investigations/export` or `/investigations/upload/export` (same inputs as above, returns `text/markdown` with a `Content-Disposition: attachment` header instead of JSON)
- Interactive docs: `/docs` (Swagger) and `/redoc` — disabled automatically when `APP_ENV=production`

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

### Frontend tests & linting

```bash
cd frontend
npm run lint
npx tsc -b
npm run test
npm run build
```

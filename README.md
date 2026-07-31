# AI Incident Investigator

An AI-powered incident investigation platform: upload application logs, detect production incidents, get automated root-cause analysis and fix suggestions, and generate incident reports — built on a multi-agent architecture (LangGraph orchestration, Claude/Gemini, MCP integration, guardrails, and evaluation).

**Stack**: Python 3.12 / FastAPI / LangGraph / SQLAlchemy (backend) · React / TypeScript / Bootstrap 5 (frontend) · Claude + Gemini · Docker. **143 backend tests** (pytest, `ruff` clean) · **36 frontend tests** (Vitest + React Testing Library, `eslint`/`tsc` clean).

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for design decisions, [`docs/features/`](docs/features/) for a log of what's been built feature by feature, and [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) before cutting a release. Contributor/agent rules live in [`PROJECT_RULES.md`](PROJECT_RULES.md).

## Status

Backend foundation is in place: FastAPI + async SQLAlchemy/SQLite, Alembic migrations, OpenAPI docs, structured logging, and Docker. The frontend (React + TypeScript + Bootstrap 5, responsive sidebar layout, five pages — Dashboard/Incident Analysis/Reports/Evaluation/Settings — with charts, cards, tables, and dark mode) is also built, ahead of its original roadmap slot, and every page now calls a real, working backend endpoint. Both services are containerized with separate **development** (hot reload) and **production** (built artifacts) Compose configs. A **LangGraph multi-agent orchestrator** (`POST /api/v1/investigations`, plus `POST /api/v1/investigations/upload` for log files) analyzes logs through five agents — Monitoring, Log Analysis, Root Cause, Recommendation, Report — with Claude/Gemini swappable behind one provider interface (see `ARCHITECTURE.md` → "Multi-agent orchestration"). **Monitoring and Log Analysis are both rule-based** (regex-driven error/warning detection, severity scoring, stack-trace extraction, repeated-failure grouping, and anomaly detection — no LLM call) and need no API key at all; the three agents after them do, and only run if Monitoring actually finds an incident — logs with no errors get a full, real response with zero LLM calls. Running the deeper analysis requires an `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` (see below); without one, those requests fail fast with a clear `503` rather than an obscure error. Root Cause matches evidence against a small curated catalog of known failure patterns and produces a numeric, bounded `confidence_score` plus explicit `reasoning` — not a loose "high/medium/low" string. Recommendation groups fixes into `code_fixes`/`configuration_changes`/`database_improvements`, each with its own `rationale`, rather than a generic action list. Report assembles a professional six-section Markdown document (Summary, Root Cause, Evidence, Confidence, Recommendation, Next Steps) deterministically from the earlier agents' validated data, with only the Summary and Next Steps LLM-authored — and it can be exported as a downloadable `.md` file via `/investigations/export` or `/investigations/upload/export`, or downloaded straight from the frontend's Incident Analysis page after running an analysis. An **Agent Skills framework** (`agents/skills/`) packages domain expertise as versioned `SKILL.md` files with trigger conditions, matched into Root Cause's prompt when relevant — three bundled example skills ship today: `python`, `fastapi`, and `log_analysis`. A **Filesystem MCP server** (real [Model Context Protocol](https://modelcontextprotocol.io), mounted at `/mcp/`) exposes confirmed incidents — persisted to disk when Monitoring detects one — as five tools: read an uploaded log, save/overwrite a report, list incidents, and list/delete exported files; the same underlying storage is also exposed over plain REST (`GET /api/v1/incidents`, `GET /api/v1/incidents/{id}/report`) specifically for the frontend, since MCP's transport isn't what a browser talks to. An **evaluation module** scores every confirmed incident on response time, confidence, and rule-based root-cause/recommendation quality rubrics — the aggregate at `GET /api/v1/evaluations/summary` and every individual evaluation at `GET /api/v1/evaluations` (or `GET /api/v1/evaluations/{id}` for one) back the frontend's Dashboard card and dedicated Evaluation page, the latter also charting the aggregate quality metrics. See [`docs/features/`](docs/features/) for the full build log. The remaining target folder structure (domain persistence, MCP *client*, guardrails) is scaffolded but not yet implemented — see `ARCHITECTURE.md` for what's real vs. planned.

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
- Filesystem MCP server: `/mcp/` (real Model Context Protocol, Streamable HTTP transport) — 5 tools for reading/managing confirmed-incident artifacts persisted on disk; see `docs/features/12-filesystem-mcp.md` for example calls
- List confirmed incidents: `GET /api/v1/incidents`; fetch one's report: `GET /api/v1/incidents/{incident_id}/report` (`text/markdown`, `404` if none) — plain REST over the same storage the MCP server uses, for the frontend
- Evaluation summary: `GET /api/v1/evaluations/summary` — aggregate response time / confidence / quality-rubric scores across every confirmed incident, no LLM key needed; displayed on the frontend Dashboard and the dedicated Evaluation page. Every individual evaluation: `GET /api/v1/evaluations` (or `GET /api/v1/evaluations/{incident_id}` for one)
- Interactive docs: `/docs` (Swagger) and `/redoc` — disabled automatically when `APP_ENV=production`

> **Running the frontend from somewhere other than `http://localhost:5173`?** Set `CORS_ALLOWED_ORIGINS` in `backend/.env` (comma-separated) to match, or the browser will silently block every request — a server-to-server `curl` still works fine either way, since CORS is enforced by the browser, not the server.

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

## Known limitations

This project has no authentication/authorization layer anywhere — not on the REST API, not on the Filesystem MCP server mounted at `/mcp` (which includes a destructive `delete_exported_file` tool). That's a reasonable state for local development and this project's current scope, but **do not deploy it publicly reachable without adding an auth layer first** — see `RELEASE_CHECKLIST.md` and `ARCHITECTURE.md` → "Deferred by design" for what else is intentionally not built yet (domain persistence, guardrails, a real LLM-as-judge evaluation path).

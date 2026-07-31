# Architecture

This document explains the structural decisions behind AI Incident Investigator and is updated as new features land.

## Overview

A monorepo with a Python/FastAPI backend (`backend/`) and a React/TypeScript frontend (`frontend/`). The backend is the system of record: it owns log ingestion, persistence, and the multi-agent AI pipeline (LangGraph + Claude/Gemini). The frontend is a thin client against the backend's HTTP API.

The frontend was originally planned as a later roadmap item (after the agent pipeline), but was explicitly requested — and built — ahead of it. Its pages call service-layer functions for endpoints the backend doesn't expose yet (incidents, reports); see "Frontend" below for how that's handled honestly rather than with placeholder/mock data.

## Backend layering

The backend follows clean-architecture principles. Logic is added to a layer **only when a feature needs it there** — an empty folder is a map, not placeholder code, but a folder containing a stub function or fake return value would be, and this project's rules explicitly forbid that. The full folder skeleton below was scaffolded ahead of time (on explicit request) as a map of where things will go; each folder stays empty (tracked only by a `.gitkeep`) until the feature that owns it lands.

As of the backend-foundation work, these layers have real code in them:

- **`app/api/`** — FastAPI routers and Pydantic request/response schemas. Translates HTTP <-> application calls. No business logic lives here.
- **`app/config.py`** — a single `Settings` (Pydantic `BaseSettings`) source of truth for all environment-driven configuration, exposed via a cached `get_settings()` accessor so it's resolved once per process and easily overridden in tests.
- **`app/database.py`** — the async SQLAlchemy engine, session factory, and the `get_db_session()` FastAPI dependency that hands each request its own session.
- **`app/logging_config.py`** — structured logging configuration, applied once at app startup.
- **`app/infrastructure/database/base.py`** — the SQLAlchemy `DeclarativeBase` every ORM model will inherit from. It exists now (with zero models yet) because Alembic's autogenerate needs `Base.metadata` to diff against — see "Database migrations" below. This is infrastructure wiring, not a domain model, so it lives in `infrastructure/`, not `domain/`.

Everything else in the full layout (`domain/`, `services/`, `agents/`, `guardrails/`, `evaluation/`, `frontend/`, etc.) is scaffolded but empty — see "Full project layout" below for what each folder is for and which feature is expected to populate it.

Application/use-case logic sits between `api/` and `domain/`+`infrastructure/`, invoked from routers via constructor/parameter injection — see "Dependency injection" below.

## Dependency injection

FastAPI's built-in `Depends()` system is used directly rather than a separate DI container/framework. At this project's scale that's the idiomatic, lowest-friction choice: dependencies (DB sessions, settings, and later, repositories and LLM clients) are declared as constructor/parameter dependencies and FastAPI resolves them per-request. This keeps route handlers thin and testable — tests override dependencies (e.g. swap the DB session for one bound to a temp SQLite file) via fixtures instead of monkeypatching internals.

## Data & persistence

SQLite is the MVP datastore, accessed asynchronously via SQLAlchemy 2.0 + `aiosqlite`. It's zero-infrastructure for local dev and Docker, and the async session boundary (`AsyncSession`, `get_db_session`) is the same shape a future Postgres migration would use — swapping the driver later is a config change, not a rewrite.

## Database migrations (Alembic)

Alembic is wired using its **async template**, with `script_location` pointed at the already-scaffolded `app/infrastructure/database/migrations/` (not a separate top-level `alembic/` folder) so migrations live next to the models they version, consistent with the rest of the `infrastructure/` layer.

Two things are deliberately *not* duplicated in `alembic.ini`:

- **Database URL** — `migrations/env.py` calls `get_settings().database_url` and sets it on the Alembic config at runtime, so the same `DATABASE_URL` env var drives both the app and its migrations. `alembic.ini` leaves `sqlalchemy.url` blank.
- **Target metadata** — `env.py` imports `Base` from `app/infrastructure/database/base.py` and passes `Base.metadata`, so `alembic revision --autogenerate` will pick up every ORM model as soon as one is added — no per-model wiring needed later.

No migration files exist yet (`versions/` is empty) because there are no ORM models yet; generating an empty "baseline" migration now would just be a no-op file with nothing to justify it. The wiring itself is verified working — `alembic current` connects through the real async engine against the configured SQLite DB, locally and inside the Docker image — so Feature 2 only needs to add models and run `alembic revision --autogenerate`.

Run migrations with `uv run alembic upgrade head` (locally) or `docker compose exec backend uv run alembic upgrade head` (containerized).

## API documentation

FastAPI's built-in OpenAPI/Swagger support is configured with real metadata (`title`, `description`, `version` — sourced from `Settings.app_version`, `license_info` matching the repo's Apache-2.0 `LICENSE`, and per-tag descriptions via `openapi_tags`) rather than left at the framework defaults. `/docs` (Swagger UI), `/redoc`, and `/openapi.json` are served normally in every environment except `APP_ENV=production`, where `create_app()` sets all three URLs to `None` — interactive docs are a development/diagnostic surface and this project's rule is to not expose them publicly once the app is actually in production.

## Configuration

All runtime configuration is environment-variable driven via `Settings` (`pydantic-settings`), loaded from the process environment or an optional `.env` file. `.env.example` documents every variable; real `.env` files are gitignored. This applies uniformly to infra config now and to API keys (Claude, Gemini) in later features — secrets are never hardcoded.

## Containerization

`backend/Dockerfile` builds a slim, non-root image using `uv` (installed via `COPY --from=ghcr.io/astral-sh/uv:latest`) for fast, reproducible dependency installation from the committed `uv.lock`. Dependencies are installed in a separate layer from application code so an app-only code change doesn't invalidate the dependency-install cache layer. `frontend/Dockerfile` is a two-stage build (Node to build the static bundle, nginx to serve it — see "Frontend" above for why). The root `docker-compose.yml` orchestrates both services, gives the backend a named volume for its SQLite file so data survives container recreation, and starts the frontend only after the backend reports healthy.

## Testing

`pytest` + `pytest-asyncio` + `httpx.AsyncClient` (via `ASGITransport`, no real network socket). Each test run gets an isolated temp-file SQLite database (via the `client` fixture in `backend/tests/conftest.py`), so tests never share state with local dev data or each other.

## Frontend

**Tooling**: Vite + React 18 + TypeScript, `npm`. `react-router-dom` for routing, plain `bootstrap` (CSS + JS bundle) rather than `react-bootstrap` — the requirement was "Bootstrap 5" the CSS/component framework, and its own JS (via `data-bs-*` attributes) already drives the interactive pieces we need (offcanvas, dropdowns) without an extra abstraction layer. No global state library: React Context (`store/`) for UI state (currently just the light/dark theme) and a small `useAsync` hook (`hooks/`) for the loading/success/error pattern around API calls — neither the app's size nor its state complexity justifies Redux/Zustand/React Query yet.

**Layout**: `AppLayout` composes a sticky `Topbar` and a `Sidebar` using Bootstrap's `offcanvas-lg` pattern — a static column at the `lg` breakpoint and above, a slide-in off-canvas panel (toggled by the Topbar's hamburger button) below it. This is the officially documented Bootstrap "responsive sidebar" pattern and needs no custom show/hide state in React; each nav link also carries `data-bs-dismiss="offcanvas"` so tapping a link closes the mobile menu.

**API service layer**: `services/apiClient.ts` is a thin typed `fetch` wrapper (base URL from `config.ts`, throws a typed `ApiError` on non-2xx). Per-resource modules (`healthService.ts`, `incidentService.ts`, `reportService.ts`) each expose one typed function per endpoint. `types/` mirrors the backend's Pydantic schemas by hand (e.g. `HealthStatus` matches `HealthResponse` field-for-field) since there's no shared schema codegen yet.

**Honesty about incomplete backend coverage**: the backend only has `GET /api/v1/health` today. The Incidents and Reports pages, and the Dashboard's "recent incidents" card, call `incidentService.getIncidents()` / `reportService.getReports()` anyway — real, correctly-implemented calls against endpoints that don't exist server-side yet, so they currently render a real error state ("service not available yet") rather than fake/mock data. This was a deliberate choice: hardcoding a mock incidents array would be exactly the placeholder code this project's rules forbid, whereas a real API call with real error handling is honest, correct code that will simply start working once the backend catches up (planned for the log-upload/detection feature). The one piece of genuinely live data right now is the health status shown on the Dashboard and in the Topbar's badge.

**Settings page** is fully functional today, not a placeholder: it drives a real light/dark theme toggle via Bootstrap 5.3's native `data-bs-theme` color modes (`store/themeContext.ts` + `store/ThemeProvider.tsx`), persisted to `localStorage`, defaulting to the OS's `prefers-color-scheme`. It also displays the resolved `VITE_API_BASE_URL` for debugging.

**Environment configuration**: `src/config.ts` mirrors the backend's `Settings` pattern — one module reads `import.meta.env`, validates it (throws if `VITE_API_BASE_URL` is missing), and everything else imports the parsed `config` object rather than reading `import.meta.env` directly. Vite env vars are compile-time, not runtime, which matters for Docker (see below).

**Testing**: Vitest + React Testing Library, mirroring the backend's pytest setup. `tests/setup.ts` adds jest-dom matchers and a `matchMedia` polyfill (jsdom doesn't implement it, and `ThemeProvider` needs it for system-theme detection). Tests cover `useAsync`'s loading/success/error transitions, `Sidebar`'s nav links and active-route highlighting, and `ThemeProvider`'s theme toggle + persistence — logic, not just snapshots.

**Docker**: multi-stage build — `node:24-alpine` builds the static bundle, `nginx:1.27-alpine` serves it with an SPA fallback (`try_files ... /index.html`) so client-side routes like `/incidents` don't 404 on refresh. Because `VITE_API_BASE_URL` is baked in at build time, it's passed as a Docker build `ARG` (`docker-compose.yml` sets it to `http://localhost:8000/api/v1` — the backend's *host*-published port, since the browser calls it directly, not from inside the Docker network).

**Accepted dependency-audit findings** (`npm audit`, both dev/transitive, neither applicable here):

- `brace-expansion`/`minimatch` DoS in ESLint's dependency chain — fixed only in ESLint 10, which requires `eslint-plugin-react-hooks@7`. That major version ships a new `set-state-in-effect` rule that flags the standard "reset to loading, then fetch" pattern used by `useAsync` — an immature rule fighting a correct, common pattern. Staying on ESLint 9 / `eslint-plugin-react-hooks@5` was the more stable choice; the underlying issue only matters if untrusted glob patterns reach our own lint config, which they don't.
- React Router's "RSC Mode CSRF Bypass" (GHSA-qwww-vcr4-c8h2) — affects React Server Components / server-action handling. This app is a plain client-side SPA (`<BrowserRouter>`, no data routers, no server actions), so the vulnerable code path isn't reachable.

## Full project layout

The complete enterprise folder skeleton (folders only — no implementation yet). Each entry names the feature expected to populate it.

```text
ai-incident-investigator/
├── backend/                          FastAPI backend service — owns persistence + the agent pipeline
│   ├── src/app/
│   │   ├── api/                       [Feature 1, in use] HTTP layer: routers, request/response schemas
│   │   ├── domain/                    [Feature 2] Framework-free business layer
│   │   │   ├── entities/               Core business objects (e.g. LogFile, Incident) — plain Python/Pydantic, no ORM/HTTP imports
│   │   │   ├── repositories/            Abstract repository interfaces (ports) that infrastructure/ implements
│   │   │   └── exceptions/               Domain-level error types, independent of HTTP status codes
│   │   ├── services/                  [Feature 2+] Application/use-case layer — orchestrates domain + infrastructure, called by API routers
│   │   ├── infrastructure/            [Feature 2+] Concrete adapters implementing domain interfaces
│   │   │   ├── database/                [in use] `base.py` (declarative Base); ORM models + repository implementations land in Feature 2
│   │   │   │   └── migrations/           [in use] Alembic (async), wired to Base.metadata + Settings; no versions/ yet — first real migration lands with Feature 2's models
│   │   │   ├── llm/                     Claude + Gemini client adapters behind a common provider interface
│   │   │   └── mcp/                     Model Context Protocol integration
│   │   │       ├── client/               Consumes external MCP tool servers from within agents
│   │   │       └── server/               Exposes this app's own capabilities as an MCP server to other tools
│   │   ├── agents/                    [Feature 3+] Multi-agent architecture, orchestrated with LangGraph
│   │   │   ├── graphs/                  LangGraph graph/workflow definitions wiring nodes together
│   │   │   ├── nodes/                   Individual agent implementations (detector, root-cause analyzer, fix-suggester, reporter)
│   │   │   ├── state/                   Shared graph state schemas passed between nodes
│   │   │   ├── prompts/                 Prompt templates, one set per agent
│   │   │   └── skills/                  Reusable Agent Skills — invokable capabilities/tools shared across multiple agents
│   │   ├── guardrails/                [Feature 8] Input/output validation and safety checks wrapping LLM calls
│   │   └── evaluation/                [Feature 9] DeepEval eval suites, metrics, and harness for agent output quality
│   ├── tests/
│   │   ├── unit/                       Tests for a single module in isolation (mocks at the boundary)
│   │   ├── integration/                 Tests spanning modules (e.g. API -> service -> real test DB)
│   │   └── e2e/                          Full agent-pipeline runs against a running app instance
│   ├── Dockerfile                     [Feature 1, in use]
│   └── pyproject.toml                 [Feature 1, in use]
├── frontend/                          [in use] React + TypeScript + Bootstrap 5 client (Vite)
│   ├── public/                         Static assets served as-is (currently empty)
│   ├── src/
│   │   ├── components/                  [in use] `layout/` (AppLayout, Sidebar, Topbar, HealthBadge), `common/` (LoadingSpinner, ErrorAlert, EmptyState)
│   │   ├── pages/                        [in use] DashboardPage, IncidentsPage, ReportsPage, SettingsPage, NotFoundPage
│   │   ├── features/                      Feature-sliced modules, for when a page outgrows components/+pages/ (empty — not yet warranted)
│   │   ├── services/                      [in use] apiClient + one module per resource (health, incident, report)
│   │   ├── hooks/                          [in use] `useAsync` — shared loading/success/error state for API calls
│   │   ├── types/                          [in use] HealthStatus (mirrors backend), Incident/IncidentReport (provisional — backend doesn't expose these yet)
│   │   ├── store/                           [in use] ThemeProvider + theme context (light/dark, Bootstrap 5.3 color modes)
│   │   ├── styles/                           [in use] `custom.css` — small tweaks layered on Bootstrap's utility classes
│   │   └── utils/                             Frontend-only utility functions (empty — nothing needed yet)
│   ├── Dockerfile                      [in use] multi-stage: node build -> nginx serve, SPA fallback
│   └── tests/                          [in use] Vitest + React Testing Library
├── docs/
│   ├── features/                      [Feature 1, in use] One doc per completed feature: what was built, how to run/test it
│   ├── adr/                           Architecture Decision Records — one immutable file per significant decision and its rationale
│   ├── api/                           Generated API reference (OpenAPI export, endpoint docs)
│   └── runbooks/                      Operational guides: deployment, migrations, incident recovery for this app itself
├── scripts/                          Dev/ops helper scripts (env setup, DB seeding, OpenAPI client generation)
├── .github/
│   └── workflows/                    GitHub Actions CI/CD: backend lint+test, frontend lint+test, Docker image build, eval-suite runs
├── docker-compose.yml                [in use] Local/dev orchestration of backend + frontend
├── ARCHITECTURE.md                   This file — living record of structural decisions
├── PROJECT_RULES.md                  Standing rules for how this repo is built
└── README.md                         Project overview + quickstart
```

### Placement decisions worth calling out

- **LangGraph, agent nodes, and Agent Skills all live under `backend/src/app/agents/`**, not at the repo root. The agent pipeline is backend-internal orchestration logic, not a separately deployed service — keeping it inside the one backend that already owns persistence and the API avoids a second deployable unit with no independent reason to exist.
- **MCP lives under `infrastructure/mcp/`, split into `client/` and `server/`.** MCP is fundamentally an infrastructure integration (a protocol adapter), consistent with how `infrastructure/` already documents LLM provider adapters. `client/` is what agents use to call *other* MCP tool servers; `server/` is this app choosing to *expose* its own incident data as MCP tools to other systems — two distinct directions of the same protocol, worth keeping visually separate.
- **`services/` is a separate top-level layer, not folded into `domain/`.** Domain stays framework-free and dependency-free; `services/` is where orchestration across domain + infrastructure + agents happens and is where FastAPI routers' `Depends()` chains terminate.

## Deferred by design (not yet built)

Every folder in the layout above marked with a feature number is empty until that feature lands. Building real logic into them now, before there's an agent or endpoint that needs it, would be exactly the kind of speculative abstraction this project's rules avoid — the folders exist now only because scaffolding the map was explicitly requested independently of implementation.

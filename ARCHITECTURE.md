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
- **`app/infrastructure/llm/`**, **`app/agents/`**, **`app/services/investigation_service.py`**, **`app/api/investigations.py`** — the LangGraph multi-agent orchestrator. See "Multi-agent orchestration (LangGraph)" below.

Still empty: `domain/`, `guardrails/`, `evaluation/`, `agents/skills/`, `infrastructure/mcp/` — see "Full project layout" below for what each is for and which feature is expected to populate it.

Application/use-case logic sits between `api/` and `domain/`+`infrastructure/`, invoked from routers via constructor/parameter injection — see "Dependency injection" below.

## Dependency injection

FastAPI's built-in `Depends()` system is used directly rather than a separate DI container/framework. At this project's scale that's the idiomatic, lowest-friction choice: dependencies (DB sessions, settings, and later, repositories and LLM clients) are declared as constructor/parameter dependencies and FastAPI resolves them per-request. This keeps route handlers thin and testable — tests override dependencies (e.g. swap the DB session for one bound to a temp SQLite file) via fixtures instead of monkeypatching internals.

## Multi-agent orchestration (LangGraph)

`POST /api/v1/investigations` (raw text) and `POST /api/v1/investigations/upload` (log file) both run the same five agents over log text, orchestrated by a LangGraph `StateGraph`. Each has an `/export` counterpart (`/investigations/export`, `/investigations/upload/export`) returning just the final report as a downloadable `.md` file instead of the full JSON state — see "Export endpoints" below.

```text
Monitoring Agent (rule-based, no LLM)
      |
(incident detected?) --no--> END
      | yes
Log Analysis Agent (rule-based, no LLM)
      |
Root Cause Agent (LLM)
      |
Recommendation Agent (LLM)
      |
Report Agent (LLM)
      |
     END
```

**Shared state** (`app/agents/state/investigation_state.py`) is a single Pydantic `InvestigationState` model threaded through every node — `logs` in, then each agent writes the field(s) it owns (`monitoring`, `log_analysis`, `root_cause`, `recommendations`, `report`) and never another agent's field. LangGraph node functions return a `dict` of just the fields they're updating; LangGraph merges it into the running state.

**Monitoring and Log Analysis are both deterministic, not LLM-backed.** Monitoring (`monitoring_agent.py` + `log_parser.py`) classifies each log line by regex against common level markers (`CRITICAL`/`FATAL`/`ERROR`/`SEVERE`, `WARN`/`WARNING`, plus Python tracebacks), counts errors and warnings, and maps the counts to a `Severity` tier (`none`/`low`/`medium`/`high`/`critical`) via documented thresholds. Log Analysis (`log_analysis_agent.py` + `log_analyzer.py`) goes deeper over the same raw text: it extracts full Python stack traces (exception type, message, raw frames), groups error lines into `RepeatedFailure`s by a normalized signature (stripping timestamps and collapsing digits, so "timed out after 3013ms" and "timed out after 4502ms" are recognized as the same recurring failure rather than two unrelated ones), flags two concrete rule-based anomalies (an isolated CRITICAL/FATAL event, and a burst of `_BURST_MIN_ERRORS`+ errors within `_BURST_WINDOW_SECONDS`), and pulls out affected component names.

This is a deliberate choice for both, not a shortcut: parsing, extraction, counting, and grouping are mechanical tasks regex and simple data structures handle reliably and cheaply — an LLM would be slower, costlier, and *worse* at exact counting for zero benefit. LLM reasoning is reserved for the three agents that actually need judgment — inferring a root cause, weighing recommendations, writing prose. A useful side effect: both agents are fully unit-testable (`tests/unit/test_log_parser.py`, `tests/unit/test_log_analyzer.py`) with no API key and no network access at all — 20 of this project's test cases exercise pipeline logic without ever needing an LLM.

Log Analysis re-parses `state.logs` independently rather than reusing Monitoring's classification: `MonitoringResult` caps its sample lists at 20 entries each (for a bounded API response), but repeated-failure counting and anomaly detection need the *full* uncapped set. Re-running this cheap, pure parse is a deliberate trade-off against threading unbounded internal data through the public response schema.

**Each LLM-backed agent is a factory, not a plain function**: `make_root_cause_agent(llm) -> node_fn` closes over an `LLMProvider` and returns the actual node function LangGraph calls with only `state`. This is how dependency injection reaches into LangGraph nodes despite LangGraph's node signature only accepting state — the *graph builder* (`build_investigation_graph(llm)`) is what's constructed with a dependency, not the individual nodes. Monitoring and Log Analysis have no such dependency and are wired in directly as plain functions.

**Structured output, not free-text parsing — all three LLM agents, including Report.** Root Cause and Recommendation are prompted to respond with *only* a JSON object matching a specific schema, parsed via `json.loads` + the matching Pydantic model (`RootCauseResult`, `RecommendationResult`), raising a clear `AgentOutputError` (mapped to HTTP 502) if the model doesn't comply — never silently accepting malformed output. Report follows the same discipline, but its JSON schema (`ReportSections`) covers only `summary` and `next_steps` — the two pieces that genuinely need LLM-authored prose. It does **not** ask the LLM to restate Root Cause, Evidence, Confidence, or Recommendation, because that data already exists, already validated, from earlier stages; asking the LLM to reproduce it in prose would risk it contradicting itself (e.g. stating a different confidence figure than `confidence_score` actually holds) for no benefit. `report_renderer.py`'s `render_incident_report_markdown()` deterministically assembles the full six-section document — **Summary, Root Cause, Evidence, Confidence, Recommendation, Next Steps**, always in that order, always all six present — from the validated state plus the LLM's two fields. `categorize_confidence_label()` maps `confidence_score` to a High/Medium/Low label (thresholds at 0.8 and 0.5) shown alongside the raw percentage.

**Root Cause is the one agent matched against a known-pattern catalog.** `agents/nodes/failure_patterns.py` is a small, curated list of common production-incident patterns (connection pool exhaustion, cascading timeout, resource exhaustion, null reference, deadlock/contention, configuration error, dependency outage, traffic spike), rendered into the system prompt. The agent's `matched_pattern` field must be one of those names or `null` — never a free-form guess — and the node validates that itself: a name outside the catalog raises `AgentOutputError` just like malformed JSON would, since a hallucinated pattern name is exactly the kind of malformed output the rest of the pipeline already refuses to accept silently. `confidence_score` is a `float` constrained to `[0.0, 1.0]` via a Pydantic `Field` (not a loose string like `"high"`), and `reasoning` is a required, separate field from `hypothesis` — the claim and the justification for it are distinct, both explicit in the schema, both fed forward into Recommendation and Report.

**Recommendation groups fixes by category, each with its own rationale.** `RecommendationResult` has three required lists — `code_fixes`, `configuration_changes`, `database_improvements` — each a `Recommendation` (`description` + `rationale`), not a bare string. An empty list for a category is expected and correct (most incidents don't need a database change); the prompt explicitly tells the model not to pad a category just to fill it. What the node *does* reject: every category empty at once. A confirmed root cause with zero actionable recommendations across all three categories is itself a malformed response, so `recommendation_agent.py` raises `AgentOutputError` in that case — the same "fail loudly, don't paper over it" stance as the pattern-catalog check above.

**The conditional edge after Monitoring is a real short-circuit, not decoration**: if the Monitoring Agent finds no errors, `_route_after_monitoring` routes straight to `END` — Log Analysis and the three LLM agents never run. This is the one place in the graph where control flow depends on a node's output rather than always proceeding to the next step, and it's the reason Monitoring being LLM-free matters practically, not just architecturally: an investigation of clean logs completes without needing an LLM configured at all (verified — see below).

**Fail fast on misconfiguration, but lazily**: `infrastructure/llm/factory.py`'s `build_llm_provider()` raises `LLMConfigurationError` immediately if the selected provider's API key isn't set — but that construction is deferred by `_LazyLLMProvider` until the *first actual `complete()` call*, not at FastAPI dependency-resolution time. This matters because FastAPI resolves `Depends(get_llm_provider)` for every request regardless of whether the request will end up needing it; without the lazy wrapper, every request would fail with 503 the moment an LLM key is missing, even ones that short-circuit at Monitoring and never touch the LLM. `main.py` maps `LLMConfigurationError` to HTTP 503. Verified in this environment (no API key configured): a clean-log request returns `200` with a full triage result; a request whose logs contain real errors correctly runs both deterministic agents (confirmed via direct invocation — stack trace extracted, repeated failures grouped with correct counts, both anomaly rules fired) and then fails with a clear `503` only once Root Cause actually needs the LLM.

**Two providers, one interface**: `LLMProvider` (`infrastructure/llm/provider.py`) is a `Protocol` with one method, `complete(system, prompt) -> str`. `AnthropicProvider` and `GeminiProvider` both implement it; `factory.get_llm_provider()` (cached, like `get_settings()`) selects between them via `Settings.llm_provider`. Neither adapter's real network path has been exercised in this environment — there's no API key configured here to test against — only the interface contract and the graph's orchestration logic (via a `FakeLLMProvider` test double) have been verified. Swapping providers, or pointing `GeminiProvider`'s model string at whatever Google's current model ID is at deploy time, requires no changes to any agent.

**File upload**: `POST /api/v1/investigations/upload` accepts a log file (multipart, `UploadFile`), enforces a 5 MiB limit (`413`) and UTF-8 decoding (`400`), then delegates to the exact same `run_investigation()` used by the raw-text endpoint — no duplicated business logic, only the HTTP-specific input translation differs. That validation (`_read_uploaded_logs()`) is itself shared with the upload/export endpoint below, so both enforce identical limits.

**Export endpoints**: `POST /api/v1/investigations/export` and `/investigations/upload/export` run the identical pipeline but return `Response(content=result.report, media_type="text/markdown", headers={"Content-Disposition": 'attachment; filename="incident-report.md"'})` instead of the JSON state — a real file download, for a human who wants the report itself rather than the underlying data. If Monitoring found no incident, `result.report` is `None` and the endpoint returns `422` ("no incident was detected, so there is no report to export") rather than a broken empty download.

**Why this is stateless (no persistence yet)**: both endpoints take logs as input and return the final state in the response — neither reads from nor writes to the database. Wiring this to persisted `LogFile`/`Incident` domain entities is Feature 2 (log upload & storage), still pending; building that persistence layer now, before there was a pipeline to consume it, would have been exactly the kind of speculative abstraction this project avoids.

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

Both Dockerfiles are **multi-stage with named `development` and `production` targets**, sharing a common `base` stage (dependency installation) so neither mode re-solves/re-downloads dependencies independently:

- **`backend/Dockerfile`**: `base` installs `uv` (via `COPY --from=ghcr.io/astral-sh/uv:latest`) and syncs dependencies from the committed `uv.lock`, in a layer separate from application code so an app-only change doesn't invalidate the dependency-install cache. `development` includes the dev dependency group (pytest, ruff) and runs `uvicorn --reload`. `production` installs with `--no-dev`, copies only `src/` and `alembic.ini` (no tests), and runs uvicorn without reload. Both run as a non-root user.
- **`frontend/Dockerfile`**: `base` runs `npm ci`. `development` runs the Vite dev server with HMR. A separate `build` stage runs `npm run build` (with `VITE_API_BASE_URL` baked in via a build `ARG`, since Vite env vars are compile-time for a production bundle), and `production` copies that build's `dist/` into an `nginx:1.27-alpine` image with an SPA-fallback `nginx.conf`.

The **default target for a bare `docker build .`** (no `--target` flag) is `production` in both Dockerfiles, since that's the safer thing to produce if someone builds without specifying a mode.

### Two Compose files, not one file plus an override

- **`docker-compose.yml`** — development, and the default (`docker compose up --build`). Both services run with hot reload; `backend/src`, `backend/tests`, and `backend/alembic.ini` are bind-mounted from the host over the `development` image (so edits take effect without a rebuild — verified by editing a response field live and seeing it reflected immediately), and likewise `frontend/src`, `frontend/tests`, `frontend/public`, and `frontend/index.html`. The SQLite file is bind-mounted straight to `backend/data/` on the host (not a named volume), so it's inspectable the same way it is for a non-Docker `uv run` — no Docker-specific tooling needed to look at it.
- **`docker-compose.prod.yml`** — production, used standalone: `docker compose -f docker-compose.prod.yml up --build`. Both services run their built artifacts (no source mounted), `APP_ENV=production` (which also disables the backend's `/docs`/`/redoc` — see "API documentation" above), and the SQLite file lives in a named Docker volume (`backend_data`) rather than a host path, since a real managed volume — decoupled from host filesystem layout — is the appropriate choice once this isn't just local dev.

These are **two independent files, not a base file plus a `docker-compose.override.yml`** merged on top of it. Compose merges list-valued fields (like `ports`) by concatenation, not replacement; dev and prod differ in exactly those list-valued fields for the frontend service (different build target, different exposed port, different volumes), so layering one on top of the other would try to publish the frontend's port twice instead of switching it. Two self-contained files sidestep that merge-semantics footgun entirely, and as a side benefit each one is fully readable on its own — no mental diffing required to know what's actually running.

Both are verified end-to-end: dev mode's hot reload was confirmed for both services (a live source edit appeared in the running response/served module without a rebuild); prod mode was confirmed to serve built artifacts only, with docs disabled and Alembic still working against the named volume.

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

**Docker**: `development`/`production` targets (dev server with HMR vs. `node:24-alpine` build → `nginx:1.27-alpine` serve with an SPA fallback so client-side routes like `/incidents` don't 404 on refresh) — see "Containerization" below for the full dev/prod story, including why `VITE_API_BASE_URL` is a build `ARG` in production but a plain runtime env var in development.

**Accepted dependency-audit findings** (`npm audit`, both dev/transitive, neither applicable here):

- `brace-expansion`/`minimatch` DoS in ESLint's dependency chain — fixed only in ESLint 10, which requires `eslint-plugin-react-hooks@7`. That major version ships a new `set-state-in-effect` rule that flags the standard "reset to loading, then fetch" pattern used by `useAsync` — an immature rule fighting a correct, common pattern. Staying on ESLint 9 / `eslint-plugin-react-hooks@5` was the more stable choice; the underlying issue only matters if untrusted glob patterns reach our own lint config, which they don't.
- React Router's "RSC Mode CSRF Bypass" (GHSA-qwww-vcr4-c8h2) — affects React Server Components / server-action handling. This app is a plain client-side SPA (`<BrowserRouter>`, no data routers, no server actions), so the vulnerable code path isn't reachable.

## Full project layout

The complete enterprise folder skeleton (folders only — no implementation yet). Each entry names the feature expected to populate it.

```text
ai-incident-investigator/
├── backend/                          FastAPI backend service — owns persistence + the agent pipeline
│   ├── src/app/
│   │   ├── api/                       [in use] HTTP layer: routers, request/response schemas (health, investigations)
│   │   ├── domain/                    [Feature 2] Framework-free business layer
│   │   │   ├── entities/               Core business objects (e.g. LogFile, Incident) — plain Python/Pydantic, no ORM/HTTP imports
│   │   │   ├── repositories/            Abstract repository interfaces (ports) that infrastructure/ implements
│   │   │   └── exceptions/               Domain-level error types, independent of HTTP status codes
│   │   ├── services/                  [in use] `investigation_service.py` — builds the graph, runs it, returns the final state
│   │   ├── infrastructure/            Concrete adapters implementing domain/external interfaces
│   │   │   ├── database/                [in use] `base.py` (declarative Base); ORM models + repository implementations land in Feature 2
│   │   │   │   └── migrations/           [in use] Alembic (async), wired to Base.metadata + Settings; no versions/ yet — first real migration lands with Feature 2's models
│   │   │   ├── llm/                     [in use] `LLMProvider` Protocol + `AnthropicProvider`/`GeminiProvider` adapters + cached factory
│   │   │   └── mcp/                     Model Context Protocol integration
│   │   │       ├── client/               Consumes external MCP tool servers from within agents
│   │   │       └── server/               Exposes this app's own capabilities as an MCP server to other tools
│   │   ├── agents/                    [in use] Multi-agent architecture, orchestrated with LangGraph — see "Multi-agent orchestration" above
│   │   │   ├── graphs/                  [in use] `investigation_graph.py` — the compiled `StateGraph`
│   │   │   ├── nodes/                   [in use] `monitoring_agent.py`+`log_parser.py` and `log_analysis_agent.py`+`log_analyzer.py` (both rule-based); `failure_patterns.py` (Root Cause's catalog); `report_renderer.py` (deterministic template); a factory per LLM agent: root_cause, recommendation, report
│   │   │   ├── state/                   [in use] `InvestigationState` + per-agent result models
│   │   │   ├── prompts/                 [in use] System/user prompt builders, one set per agent
│   │   │   └── skills/                  Reusable Agent Skills — invokable capabilities/tools shared across multiple agents (still empty — no tool-calling yet)
│   │   ├── guardrails/                [Feature 8] Input/output validation and safety checks wrapping LLM calls
│   │   └── evaluation/                [Feature 9] DeepEval eval suites, metrics, and harness for agent output quality
│   ├── tests/
│   │   ├── unit/                       [in use] `test_investigation_graph.py` — graph/node behavior via a fake LLM provider
│   │   ├── integration/                 [in use] `test_investigations_api.py` — the real HTTP layer, LLM dependency overridden
│   │   └── e2e/                          Full agent-pipeline runs against a running app instance
│   ├── Dockerfile                     [in use] multi-stage: shared `base` -> `development` (uv sync w/ dev deps, --reload) / `production` (--no-dev, no reload)
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
│   ├── Dockerfile                      [in use] multi-stage: shared `base` -> `development` (vite dev + HMR) / `build` -> `production` (nginx serve, SPA fallback)
│   └── tests/                          [in use] Vitest + React Testing Library
├── docs/
│   ├── features/                      [Feature 1, in use] One doc per completed feature: what was built, how to run/test it
│   ├── adr/                           Architecture Decision Records — one immutable file per significant decision and its rationale
│   ├── api/                           Generated API reference (OpenAPI export, endpoint docs)
│   └── runbooks/                      Operational guides: deployment, migrations, incident recovery for this app itself
├── scripts/                          Dev/ops helper scripts (env setup, DB seeding, OpenAPI client generation)
├── .github/
│   └── workflows/                    GitHub Actions CI/CD: backend lint+test, frontend lint+test, Docker image build, eval-suite runs
├── docker-compose.yml                [in use] Development mode (default) — hot reload, bind-mounted source, host-visible SQLite file
├── docker-compose.prod.yml           [in use] Production mode (standalone, `-f` explicit) — built artifacts, named volume, no reload
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

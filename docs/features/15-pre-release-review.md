# Feature 15: Pre-Release Review

A full-project review ahead of the first release: remove duplicate code, improve architecture, improve documentation, improve performance, improve security, add missing tests, improve the README, verify Docker, verify frontend/backend integration, and verify every feature still works.

## What was found and fixed

**Critical: no CORS middleware existed.** The frontend's `fetch()` calls to the backend were genuine cross-origin requests (different ports), and the backend never sent `Access-Control-Allow-Origin` — every real browser request was silently blocked, even though the app "worked" in every prior curl/httpx-based verification (neither enforces CORS). Fixed with `Settings.cors_allowed_origins` + `CORSMiddleware` in `main.py`. See `ARCHITECTURE.md` → "Pre-release review" for the full story.

**Backend duplication removed**: `app/api/common.py`'s `translate_to_404()` (incidents.py + evaluations.py shared the same try/except-to-404 shape); `infrastructure/mcp/server/tools.py`'s `_call_store()` (the same off-thread-call-and-translate-errors shape existed four times).

**Frontend duplication removed**: `components/common/AsyncSection.tsx` (the loading/error/empty/success block, previously copy-pasted seven times); `utils/format.ts` (`formatPercent`/`formatSeconds`, previously defined twice); `components/incidents/ReportViewer.tsx` (a duplicated report-display block); a double-computed `severityDistribution()` call on the Dashboard.

**Security**: `InvestigationRequest.logs` gained the same 5 MiB `max_length` its upload-endpoint sibling already enforced (previously unbounded, feeding directly into LLM prompts). The download filename on Incident Analysis is now sanitized to safe characters. Two findings were documented rather than code-fixed — see "Known gaps" in `ARCHITECTURE.md`.

**Tests added**: backend `test_config.py` (Settings/CORS parsing) and an integration test proving `AgentOutputError` reaches the client as a real 502; frontend tests for `apiClient`, `formatIncidentTimestamp`, `format.ts`, `SeverityBadge`, `ReportsPage`/`IncidentReportBrowser`, and a new `App.test.tsx` exercising navigation across all 5 routes plus the 404 fallback.

**Docker verified for real**: both Compose files were actually built and run (not just `docker compose config`), including a live CORS preflight against the running container, confirmation that production disables `/docs`, and confirmation of the frontend's SPA fallback.

## How this was done

Two `general-purpose` subagents audited the backend and frontend independently (read-only), each covering duplication, architecture, security, performance, and test-coverage gaps. Findings were triaged: real bugs and duplication were fixed directly; two findings (no auth anywhere, and the artifact store's O(n) directory scan) were deliberately left as documented limitations rather than half-fixed, since a partial/easy-to-misconfigure fix would create false confidence rather than real safety.

## How to run it

Same as always — nothing about how the app runs changed, only what's now correct/tested/documented:

```bash
cd backend && uv sync && uv run uvicorn app.main:app --app-dir src --reload
cd frontend && cp .env.example .env && npm install && npm run dev
```

If the frontend runs anywhere other than `http://localhost:5173`, set `CORS_ALLOWED_ORIGINS` in `backend/.env` to match.

## How to test it

```bash
cd backend && uv run pytest -v && uv run ruff check .
cd frontend && npm run test && npm run lint && npx tsc -b && npm run build
```

Docker:

```bash
docker compose up --build                              # dev
docker compose -f docker-compose.prod.yml up --build    # prod
```

## Verification performed

- Backend: `uv run pytest -v` — **143/143 passing** (up from 135; +8 across `test_cors.py`, `test_config.py`, and the new 502 integration test). `uv run ruff check .` — clean.
- Frontend: `npm run test` — **36/36 passing** (up from 16; +20 across `apiClient.test.ts`, `formatIncidentTimestamp.test.ts`, `format.test.ts`, `SeverityBadge.test.tsx`, `ReportsPage.test.tsx`, `App.test.tsx`). `npm run lint`, `npx tsc -b`, `npm run build` — clean.
- **Docker, live**: `docker compose up` (dev) and `docker compose -f docker-compose.prod.yml up` (prod) both built and reached a healthy state; a real `curl -H "Origin: http://localhost:5173"` OPTIONS preflight against the running backend returned genuine `Access-Control-Allow-Origin`/`Access-Control-Allow-Methods` headers in both modes; production's `/docs` returned a real `404`; the frontend's SPA fallback correctly served the app for a client-side route (`/incident-analysis`) instead of nginx 404ing it; a real `POST /investigations` round-tripped through the running prod stack.
- **Every feature (1-14) re-verified**: the full backend test suite exercises Monitoring, Log Analysis, Root Cause, Recommendation, Report, Agent Skills, Filesystem MCP, and the Evaluation module end-to-end; the frontend suite exercises all 5 pages and the routing between them.

## Decisions worth calling out

- **Two findings were documented, not code-fixed**: no authentication anywhere (REST or MCP), and `IncidentArtifactStore`'s O(n) directory scan on every list call. Both have real fixes (an auth layer; the already-deferred domain-persistence database), and both would have been made worse, not better, by a quick partial patch here. See `README.md` → "Known limitations" and `RELEASE_CHECKLIST.md`.
- **Two subagents audited backend and frontend independently** rather than one pass over everything — parallelizable, read-only research is exactly the case for delegating, and kept the main context free for actually applying fixes.
- **The CORS fix's own test asserts the negative case too** (`test_disallowed_origin_gets_no_cors_header`) — a CORS test that only checks the happy path can't catch a future `allow_origins=["*"]` regression.

## What's next

Per `RELEASE_CHECKLIST.md`: add an authentication layer before any public deployment; domain-level persistence (a real database, replacing the filesystem-only incident store) would also resolve the O(n) listing concern as a side effect. Guardrails and a real LLM-as-judge evaluation path remain on the original roadmap.

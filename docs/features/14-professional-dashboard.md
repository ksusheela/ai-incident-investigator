# Feature 14: Professional Bootstrap Dashboard

Rebuilds the frontend from a 4-page skeleton (two of whose pages permanently erroed against nonexistent backend endpoints) into a real 5-page dashboard — Dashboard, Incident Analysis, Reports, Evaluation, Settings — with charts, cards, tables, dark mode, and a responsive layout. Adds the small set of backend REST endpoints needed to back it honestly with real data.

## What was built

**Backend** — new read-only REST endpoints over data the Filesystem MCP server already persists:

- `app/api/incidents.py` — `GET /incidents` (list, most recent first) and `GET /incidents/{incident_id}/report` (the persisted Markdown report, `404` if none).
- `app/api/evaluations.py` — extended with `GET /evaluations` (every stored evaluation, most recent first) and `GET /evaluations/{incident_id}` (one incident's evaluation, `404` if none), alongside the existing `GET /evaluations/summary`.
- `IncidentArtifactStore.list_evaluations()` now sorts by `evaluated_at` descending, matching `list_incidents()`'s existing contract.

**Frontend**:

- `pages/IncidentAnalysisPage.tsx` (replaces `IncidentsPage.tsx`) — a form that runs `POST /investigations` over pasted log text and renders the full pipeline output (Monitoring, Log Analysis, Root Cause with a confidence bar, grouped Recommendations, the report with a client-side Markdown download), plus a browser over past incidents.
- `pages/ReportsPage.tsx` — rebuilt as a real incident-report browser.
- `components/incidents/IncidentReportBrowser.tsx` — the shared list-incidents-and-view-a-report implementation behind both pages above.
- `pages/EvaluationPage.tsx` (new) — the aggregate summary plus a bar chart of confidence/root-cause-quality/recommendation-quality, and a full table of every individual evaluation.
- `pages/DashboardPage.tsx` — `RecentIncidentsCard` now renders real incidents; a new `SeverityDistributionCard` charts incident counts by severity.
- `components/charts/BarChart.tsx` — a hand-rolled SVG bar chart built to the "dataviz" skill's mark spec (capped thickness, top-rounded/baseline-square bars, hairline baseline, direct value + category labels, per-bar hover/focus tooltip).
- `components/common/SeverityBadge.tsx` — one severity-badge implementation, sharing its color roles with the severity chart.
- `services/investigationService.ts` (new), `incidentService.ts`/`evaluationService.ts` (extended), `apiClient.ts` (`post()`/`getText()` added).
- `styles/custom.css` — the dataviz status/chart color roles, theme-aware via the same `[data-bs-theme]` attribute `ThemeProvider` already drives.
- `components/layout/Sidebar.tsx` / `App.tsx` — updated to the 5-page structure.

See `ARCHITECTURE.md` → "Frontend dashboard" for the full design reasoning, including why REST endpoints were added alongside (not instead of) the Filesystem MCP server, and the chart color/form choices.

## Why REST endpoints, when Feature 12 deliberately kept this MCP-only

Feature 12's `list_incidents`/report-reading tools were exposed **only** through MCP, reasoning that a REST mirror would just be "a bespoke API shape wearing MCP's name." That reasoning holds for an AI-agent-facing capability, but a browser's `fetch()` isn't an MCP client — routing routine dashboard page loads through JSON-RPC/Streamable HTTP would mean hand-rolling protocol framing in `apiClient.ts` for no benefit over plain REST. Both surfaces read the same `IncidentArtifactStore`; neither depends on the other.

## Why hand-rolled SVG bars, not a charting library

Two small, static bar charts don't justify a new dependency (Recharts/Chart.js/etc.) — a ~100-line component gives full control over the exact mark spec the "dataviz" skill calls for (rounded-top-only bars, a specific baseline/label treatment) without fighting a library's defaults, and keeps the frontend's existing "no unnecessary abstraction" posture intact.

## How to run it

```bash
cd backend
uv sync
uv run uvicorn app.main:app --app-dir src --reload
```

```bash
curl http://localhost:8000/api/v1/incidents
curl http://localhost:8000/api/v1/evaluations
```

```bash
cd frontend
cp .env.example .env   # first time only
npm install
npm run dev
```

Visit `http://localhost:5173` — Dashboard, Incident Analysis, Reports, Evaluation, and Settings are all reachable from the sidebar. Run the backend alongside it to see real data instead of empty states.

## How to test it

```bash
cd backend && uv run pytest -v && uv run ruff check .
cd frontend && npm run test && npm run lint && npx tsc -b && npm run build
```

## Verification performed

- Backend: `uv run pytest -v` — 135/135 passing (9 new: `test_incidents_api.py`'s list/report/404 cases, `test_evaluations_api.py`'s new list/single/404 cases, `test_artifact_store.py`'s `list_evaluations()` sort-order test). `uv run ruff check .` — clean.
- Frontend: `npm run test` — 16/16 passing (8 new, across `BarChart.test.tsx`, `EvaluationPage.test.tsx`, `IncidentAnalysisPage.test.tsx`, and expanded `DashboardPage.test.tsx`/`Sidebar.test.tsx` coverage). `npm run lint`, `npx tsc -b`, and `npm run build` all clean.
- **Live, end-to-end, with real data**: started the server against a scratch artifact directory, persisted a real (fake-LLM-backed) investigation directly through `run_investigation()`, then confirmed `GET /incidents` (correct summary), `GET /incidents/{id}/report` (the real rendered Markdown), `GET /evaluations` and `GET /evaluations/{id}` (exact-matching confidence/quality numbers), and both `404` paths for an unknown incident id.
- **Not performed**: in-browser visual verification (actually clicking through the running app). No browser-automation tool was available in this environment, so this feature's UI correctness rests on the component test suite (real rendered DOM assertions via React Testing Library) and the live API verification above, not a human/visual pass — worth a manual look before shipping.

## Decisions worth calling out

- **Severity badges and the severity chart share one color source** (`--viz-status-*` custom properties in `custom.css`) — a severity reads the same way in a table cell, a badge, or a bar, rather than three independent color choices that could drift.
- **The confidence bar on Incident Analysis is a Bootstrap `.progress`, not a third chart** — a single ratio against a 0–100% ceiling is exactly the "meter" case the dataviz skill's form-choice table calls out as *not* warranting a bespoke chart.
- **The report's Markdown is rendered as preformatted text, not parsed into HTML** — adding a Markdown-rendering dependency for one `<pre>` block wasn't justified by this feature's scope; the report is already human-readable Markdown either way.
- **`IncidentReportBrowser` was extracted as a shared component** because Reports and Incident Analysis need the exact same behavior, not because of speculative future reuse.

## What's next

Per the original roadmap: domain-level persistence (Feature 2), guardrails, and a real DeepEval/LLM-as-judge evaluation path all remain pending. A manual in-browser pass (or wiring up a browser-automation tool) would be the natural next check on this feature specifically, since it wasn't possible here.

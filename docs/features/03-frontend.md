# Feature 3: React + TypeScript Frontend

Built ahead of its original roadmap slot (after the agent pipeline) at explicit request. See `ARCHITECTURE.md` → "Frontend" for full reasoning; this doc covers what was built and how to run/verify it.

## What was built

- **Vite + React 18 + TypeScript** app in `frontend/`, with `react-router-dom` routing and plain Bootstrap 5 (CSS + JS bundle).
- **Responsive layout**: `AppLayout` + `Topbar` + `Sidebar`, using Bootstrap's `offcanvas-lg` pattern — static column at `lg`+, slide-in panel below it, toggled by the Topbar's hamburger button.
- **Pages**: Dashboard (live health status + recent-incidents preview), Incidents (table), Reports (list), Settings (real light/dark theme toggle + API base URL display), NotFound.
- **API service layer**: `services/apiClient.ts` (typed `fetch` wrapper) + `healthService.ts` / `incidentService.ts` / `reportService.ts`, with `types/` mirroring backend schemas.
- **`useAsync` hook** — shared loading/success/error handling for every page that calls the API.
- **Environment configuration**: `src/config.ts`, `.env.example` documenting `VITE_API_BASE_URL`.
- **Theme system**: `store/themeContext.ts` + `store/ThemeProvider.tsx`, using Bootstrap 5.3's native `data-bs-theme`, persisted to `localStorage`.
- **Tests**: Vitest + React Testing Library (`useAsync`, `Sidebar`, `ThemeProvider`).
- **Docker**: multi-stage `frontend/Dockerfile` (Node build → nginx serve, SPA fallback), wired into the root `docker-compose.yml`.

## Important: what's real vs. what's honestly incomplete

The backend currently only exposes `GET /api/v1/health`. The Incidents page, Reports page, and the Dashboard's incidents card call real, correctly-written API functions against endpoints (`/incidents`, `/reports`) that don't exist on the backend yet — so right now they render a real, handled error state ("service not available yet"), not mock data. This is intentional: hardcoded mock arrays would be placeholder code, which this project's rules forbid; a real API call with real error handling is honest and will simply start working once the backend catches up. The Settings page's theme toggle and the health badge/card, by contrast, are fully live today.

## How to run it

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Visit `http://localhost:5173`. Run the backend too (`cd backend && uv run uvicorn app.main:app --app-dir src --reload`) to see the live health status instead of an "unreachable" badge.

Via Docker Compose (from repo root), runs both services together:

```bash
docker compose up --build
```

Frontend at `http://localhost:5173`, backend at `http://localhost:8000`.

## How to test it

```bash
cd frontend
npm run lint
npx tsc -b
npm run test
npm run build
```

## Verification performed

- `npx tsc -b` — clean
- `npm run lint` — clean
- `npm run test` — 5/5 passing (`useAsync` loading/success/error, `Sidebar` nav links + active-route highlighting, `ThemeProvider` toggle + persistence)
- `npm run build` — production bundle builds successfully
- `npm run dev` + curl checks — dev server serves the SPA shell and correctly falls back to `index.html` for client-side routes (e.g. `/incidents`)
- `docker compose up --build` — both containers built and started; backend reported `healthy`; frontend served content and its own `/health` endpoint responded; SPA fallback confirmed working through nginx

## Decisions worth calling out

- **No mock data** — Incidents/Reports pages call the real (currently 404ing) service functions and show a real error state, rather than hardcoded arrays. See `ARCHITECTURE.md`.
- **No heavy state library** — React Context for theme, a small `useAsync` hook for server state. Neither Redux nor React Query is justified at this size yet.
- **Two `npm audit` findings accepted, not silently ignored** — documented in `ARCHITECTURE.md` with reasoning (ESLint's minimatch DoS is dev-only and the fix forces an immature lint rule; React Router's RSC-mode CSRF bypass doesn't apply to this app's plain client-side routing).

## What's next

Per the original roadmap, still pending: LLM provider abstraction, LangGraph multi-agent pipeline, MCP integration, guardrails, evaluation — each of which will let the Incidents/Reports pages built here start rendering real data instead of "not available yet".

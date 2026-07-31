# Feature 4: Containerization — Development & Production Modes

Both services already had a working Dockerfile and were wired into a single `docker-compose.yml` (see features 01 and 03). This feature splits that into explicit **development** and **production** modes, since the previous single compose file only really supported a production-like setup (built frontend bundle, no reload, no source mounts).

## What was built

- **`backend/Dockerfile`** — restructured into a shared `base` stage plus `development` (dev dependency group included, `uvicorn --reload`) and `production` (`--no-dev`, no reload, only `src/`+`alembic.ini` copied in) targets. Default target for a bare `docker build .` is `production`.
- **`frontend/Dockerfile`** — restructured into `base` (`npm ci`), `development` (Vite dev server with HMR), `build` (production bundle, `VITE_API_BASE_URL` baked in via build `ARG`), and `production` (nginx serving the built bundle). Default target for a bare `docker build .` is `production`.
- **`docker-compose.yml`** — now the **development** config and the default (`docker compose up --build`). Bind-mounts `backend/src`, `backend/tests`, `backend/alembic.ini`, and `backend/data` (host-visible, not a named volume) into the backend container; bind-mounts `frontend/src`, `frontend/tests`, `frontend/public`, and `frontend/index.html` into the frontend container. Both run with hot reload.
- **`docker-compose.prod.yml`** (new) — the **production** config, used standalone: `docker compose -f docker-compose.prod.yml up --build`. Built artifacts only, no mounts, `APP_ENV=production`, SQLite in a named Docker volume (`backend_data`).
- **`backend/.dockerignore`** — removed the `tests/` exclusion so the `development` target's `COPY . .` (and a standalone `docker run` of that image) actually includes the test suite; the `production` target was never affected since it only ever copies `src/` explicitly.

## Why two separate compose files, not an override

Docker Compose's default `docker-compose.override.yml` mechanism merges list-valued fields (like `ports`) by **concatenation**, not replacement. Dev and prod differ in exactly those list-valued fields for the frontend service — different build target, different exposed port (`5173:5173` vs `5173:8080`), different volumes — so layering an override on top of a shared base would try to publish the frontend's port twice instead of switching modes. Two fully independent files sidestep that footgun and are each readable standalone.

## How to run it

**Development** (default):
```bash
docker compose up --build
```
Backend at `http://localhost:8000` (hot reload, `/docs` enabled), frontend at `http://localhost:5173` (Vite HMR).

**Production**:
```bash
docker compose -f docker-compose.prod.yml up --build
```
Same ports, but built artifacts only: backend runs without `--reload` and with `/docs` disabled (`APP_ENV=production`), frontend is the static bundle served by nginx.

## Verification performed

- **Dev mode**: `docker compose up --build` — both containers started, backend reported healthy, `/api/v1/health` returned `app_env: "local"`, `/docs` returned 200.
  - **Backend hot reload**: added a field to the health response on the host while the container was running, `curl`'d `/api/v1/health` again with no rebuild — the new field appeared immediately.
  - **Frontend HMR**: edited `DashboardPage.tsx`'s heading on the host, confirmed via `docker compose exec` that the bind mount propagated the change into the container, then fetched the module directly from Vite's dev server (`/src/pages/DashboardPage.tsx`) and saw the edited text — Vite was serving live source through the mount.
- **Prod mode**: `docker compose -f docker-compose.prod.yml up --build` — both containers started, backend reported healthy, `/api/v1/health` returned `app_env: "production"`, `/docs` returned **404** (confirming docs are correctly disabled), frontend served the SPA (including `/incidents` via the nginx fallback), `docker compose exec backend uv run alembic current` succeeded against the named `backend_data` volume.
- Backend `pytest`/`ruff` re-run after the Dockerfile changes: still passing/clean (no application code was touched).

## What's next

Nothing new deferred by this feature — it's infra-only. Future features (log upload, agents, etc.) will continue using dev mode for iteration and prod mode as the deployable target.

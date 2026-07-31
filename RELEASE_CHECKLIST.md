# Release Checklist

Run through this before tagging a GitHub release. Items are grouped so a fresh reviewer (or future you) can tell at a glance what's actually been verified versus what still needs a human decision.

## 1. Code quality gates

- [ ] Backend tests pass: `cd backend && uv run pytest -v` (143 tests as of this review)
- [ ] Backend lint is clean: `uv run ruff check .`
- [ ] Frontend tests pass: `cd frontend && npm run test` (36 tests as of this review)
- [ ] Frontend lint is clean: `npm run lint`
- [ ] Frontend type-checks: `npx tsc -b`
- [ ] Frontend production build succeeds: `npm run build`
- [ ] No uncommitted changes: `git status` is clean, or everything in it is intentional

## 2. Docker

- [ ] Dev stack builds and starts: `docker compose up --build`
- [ ] Prod stack builds and starts: `docker compose -f docker-compose.prod.yml up --build`
- [ ] `GET /api/v1/health` returns `200` with `db_connected: true` in both modes
- [ ] Production disables interactive docs: `curl -o /dev/null -w '%{http_code}' http://localhost:8000/docs` returns `404` when `APP_ENV=production`
- [ ] Frontend SPA fallback works: a client-side route (e.g. `/incident-analysis`) returns `200`, not a `404`, when hit directly
- [ ] Both stacks torn down cleanly afterward: `docker compose down` / `docker compose -f docker-compose.prod.yml down -v`

## 3. Frontend/backend integration

- [ ] `CORS_ALLOWED_ORIGINS` in the backend's environment matches wherever the frontend is actually served from (default `http://localhost:5173` covers both Compose files as shipped)
- [ ] A real cross-origin request works: `curl -i -X OPTIONS <backend>/api/v1/investigations -H "Origin: <frontend-origin>" -H "Access-Control-Request-Method: POST"` returns `Access-Control-Allow-Origin` matching the frontend's origin
- [ ] A request from an origin **not** in the allow-list does **not** get an `Access-Control-Allow-Origin` header (confirms the allow-list is actually restrictive, not a wildcard)
- [ ] `frontend/.env`'s `VITE_API_BASE_URL` points at the backend the frontend will actually talk to in this environment

## 4. Security — must resolve before any public/internet-facing deployment

- [ ] **No authentication exists yet** on the REST API or the Filesystem MCP server (`/mcp`, which includes a destructive `delete_exported_file` tool). This is acceptable for local/demo use; it is **not** acceptable for a publicly reachable deployment. Add an auth layer (API key, OAuth, network-level restriction — whatever fits the deployment target) before exposing this beyond localhost/a trusted network.
- [ ] No secrets committed: `backend/.env`, `frontend/.env` are gitignored and were never `git add`ed; `git log -p -- '*.env'` (excluding `.env.example`/`.env.test`) is empty
- [ ] `ANTHROPIC_API_KEY`/`GEMINI_API_KEY` are supplied via environment/secrets manager in the target deployment, never hardcoded
- [ ] `CORS_ALLOWED_ORIGINS` is set to the real production frontend origin(s) — not left at the `localhost` dev default
- [ ] Request size limits are in place for both investigation entry points (`POST /investigations`'s `logs` field and `/investigations/upload`'s file size) — both capped at 5 MiB as of this review
- [ ] Path-traversal protection (`_validate_path_component`) still covers every place `incident_id`/`filename` reaches a filesystem path — covered by `tests/unit/test_artifact_store.py`'s parametrized traversal tests

## 5. Documentation

- [ ] `README.md` — Status section reflects what's actually built, Quickstart commands all still work, "Known limitations" is current
- [ ] `ARCHITECTURE.md` — every shipped feature has a corresponding section; "Deferred by design" accurately lists what's *not* built
- [ ] `docs/features/` — every feature has a numbered doc; the most recent one matches the latest work
- [ ] `.env.example` (backend) and `.env.example` (frontend) list every environment variable the app actually reads, with safe (non-secret) example values

## 6. Known limitations to state explicitly in the release notes

Copy these into the GitHub release description rather than letting them be discovered later:

- No authentication/authorization anywhere (see §4)
- Domain-level persistence (a real database for incidents, beyond the filesystem artifact store) is not yet built — `IncidentArtifactStore.list_incidents()`/`list_evaluations()` scan every stored incident on every call, which is fine at demo scale but won't stay fine indefinitely
- Guardrails (input/output validation and safety checks wrapping LLM calls, beyond structural Pydantic validation) are scaffolded but not implemented
- Evaluation is rule-based (presence/specificity rubrics), not a real LLM-as-judge correctness check — see `ARCHITECTURE.md` → "Evaluation module"
- MCP `client/` (consuming *other* MCP tool servers) is unbuilt; only the `server/` side (exposing this app's own data) exists

## 7. Tagging the release

- [ ] Version bumped where it's tracked (`backend/pyproject.toml`, `Settings.app_version`, `frontend/package.json`) if this is a versioned release, not just a snapshot
- [ ] `CHANGELOG` entry or release notes drafted from `docs/features/*.md` (one line per feature shipped since the last release)
- [ ] Git tag created (`git tag -a vX.Y.Z -m "..."`) and pushed (`git push origin vX.Y.Z`) — only after everything above is checked
- [ ] GitHub Release created from the tag, release notes include the "Known limitations" section above verbatim

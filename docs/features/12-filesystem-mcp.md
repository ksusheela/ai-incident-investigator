# Feature 12: Filesystem MCP Server

Builds out the `server/` side of `infrastructure/mcp/` (scaffolded since the folder-structure pass, empty until now) into a real, working [Model Context Protocol](https://modelcontextprotocol.io) server, backed by a new filesystem-based artifact store for confirmed incidents.

## What was built

- **`app/infrastructure/filesystem/artifact_store.py`** — `IncidentArtifactStore`: filesystem persistence for confirmed incidents. One directory per incident (`log.txt`, `investigation.json`, `report.md`), with methods for each of the four requested capabilities plus supporting operations (`save_incident`, `read_uploaded_log`, `save_report`/`read_report`, `list_incidents`, `list_exported_files`, `delete_exported_file`). Includes explicit path-traversal validation (`_validate_path_component`) since both `incident_id` and `filename` can arrive from an external MCP client.
- **`app/infrastructure/mcp/server/tools.py`** — `create_mcp_server(store)`: a real MCP server (official `mcp` Python SDK) exposing five tools over the store: `read_uploaded_log`, `save_report`, `list_incidents`, `list_exported_files`, `delete_exported_file`.
- **`app/services/investigation_service.py`** — now persists a confirmed incident (via the artifact store) immediately after the graph finishes, only when `monitoring.incident_detected` is true. The returned `InvestigationState.incident_id` (new field) identifies what was saved.
- **`app/main.py`** — mounts the MCP server's Streamable HTTP ASGI app at `/mcp`, and extends the app's lifespan to also run the MCP session manager for the app's lifetime.
- **`Settings.incident_artifacts_dir`** (new, default `./data/incidents`) — where the store writes.

See `ARCHITECTURE.md` → "Filesystem MCP server" for the full design, including a dedicated "How this demonstrates Model Context Protocol concepts" section.

## How the four requested capabilities map to tools

| Requirement | Tool(s) |
|---|---|
| Read uploaded logs | `read_uploaded_log(incident_id)` |
| Save reports | `save_report(incident_id, markdown)` |
| List incidents | `list_incidents(limit=50)` |
| Manage exported files | `list_exported_files(incident_id=None)`, `delete_exported_file(incident_id, filename)` |

## How this demonstrates MCP concepts (summary — full explanation in ARCHITECTURE.md)

- **Server role, not client** — this app exposing its own data via MCP, the mirror image of an agent consuming someone else's MCP tools (`infrastructure/mcp/client/`, deliberately still empty).
- **Tools with auto-derived schemas** — each tool's JSON Schema comes from its Python type hints, not a hand-written spec.
- **A standard, swappable transport** — Streamable HTTP here (fits naturally into the existing FastAPI app); the same server could run over stdio with zero tool-code changes.
- **Structured content** — list-returning tools give clients both human-readable text blocks and machine-readable structured JSON.
- **Protocol-level error semantics** — a tool raising `ValueError` becomes a client-detectable tool error, not an opaque failure.
- **Protocol-visible instructions** — the server's `instructions` string is returned in the `initialize` handshake itself, not just a docstring.

## How to run it

```bash
cd backend
uv sync
uv run uvicorn app.main:app --app-dir src --reload
```

Run an investigation (needs `ANTHROPIC_API_KEY`/`GEMINI_API_KEY` to reach a real incident; a clean-log request works with neither and persists nothing):

```bash
curl -X POST http://localhost:8000/api/v1/investigations \
  -H "Content-Type: application/json" -d '{"logs": "..."}'
# -> {"incident_id": "20260731T150034123456Z-a1b2c3d4", ...}
```

Talk to the MCP server directly (real JSON-RPC, Streamable HTTP — note the trailing slash):

```bash
curl -N http://localhost:8000/mcp/ \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"cli","version":"1.0"}}}'
```

Or inspect it in-process without any HTTP layer at all:

```bash
uv run python -c "
import asyncio
from app.infrastructure.filesystem.artifact_store import IncidentArtifactStore
from app.infrastructure.mcp.server.tools import create_mcp_server
from pathlib import Path

store = IncidentArtifactStore(root_dir=Path('./data/incidents'))
server = create_mcp_server(store)

async def main():
    print([t.name for t in await server.list_tools()])
    print((await server.call_tool('list_incidents', {})).structured_content)

asyncio.run(main())
"
```

## How to test it

```bash
cd backend
uv run pytest -v
uv run ruff check .
```

## Verification performed

- `uv run pytest -v` — 105/105 passing, including:
  - `tests/unit/test_artifact_store.py` (17 tests) — save/read/list/delete for the store directly, including path-traversal rejection for both `incident_id` and `filename`.
  - `tests/unit/test_mcp_server_tools.py` (10 tests) — all five tools called through the real MCP protocol path (`MCPServer.call_tool`), not just the store, including error translation (`ToolError`) for unknown incidents and path-traversal attempts.
  - `tests/integration/test_mcp_filesystem_integration.py` (3 tests) — the full round trip: a real API request creates a confirmed incident, and it's then read back **purely through MCP tool calls** (never touching the store directly) — log content, incident listing, and file listing all verified; a second test confirms clean logs never appear in the MCP incident listing; a third confirms `/mcp` is actually mounted on the app.
- `uv run ruff check .` — clean.
- **Live smoke test, real HTTP, real protocol**: started the server and sent an actual `initialize` JSON-RPC request to `/mcp/` with the MCP `2025-06-18` protocol envelope — got back a correct `initialize` response (capabilities, `serverInfo`, `instructions`) over the Streamable HTTP/SSE transport. This is the strongest verification in this feature: not a mock, not an in-process call, an actual protocol handshake over the wire.
- **A real bug found and fixed during testing**: `generate_incident_id()` initially used second-level timestamp precision; two incidents saved in quick succession (a realistic scenario for automated log submission) could tie on `created_at`, making `list_incidents()`'s "most recent first" ordering non-deterministic between them. Fixed by using microsecond precision instead.

## Decisions worth calling out

- **Filesystem, not a database** — matches the literal requirement, and stays a simple, independent complement to the domain-level persistence still deferred to Feature 2.
- **Persist only confirmed incidents** — clean-log investigations produce nothing worth keeping; persisting every request would clutter storage and make "list incidents" ambiguous with "list checks performed."
- **Explicit path-traversal validation**, not just trust in the store's own path-joining — both `incident_id` and `filename` are untrusted input the moment they can come from an external MCP client, not just from this project's own REST layer.
- **One combined app lifespan**, not two — FastAPI has exactly one lifespan slot; the MCP session manager's required `.run()` context is nested inside the existing startup/shutdown logging rather than the app growing a second, separate lifespan mechanism.

## What's next

Per the original roadmap: `infrastructure/mcp/client/` remains empty (nothing in this pipeline needs to consume an external MCP tool yet); guardrails and evaluation remain pending; Feature 2 (domain-level log/incident persistence) may eventually complement or supersede this lightweight filesystem store.

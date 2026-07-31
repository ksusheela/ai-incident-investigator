# Feature 6: Monitoring Agent — Deterministic Log Triage & File Upload

Upgrades the Monitoring Agent introduced in Feature 5 from a thin "ask the LLM if this is bad" call into a real, rule-based triage engine, and adds file-upload support to the investigation endpoints.

## What changed

- **`app/agents/nodes/log_parser.py`** (new) — pure, dependency-free functions:
  - `classify_log_lines(logs)` — buckets each non-blank line into errors (`CRITICAL`/`FATAL`/`ERROR`/`SEVERE`, or a Python traceback) or warnings (`WARN`/`WARNING`), and extracts the first/last leading timestamp found.
  - `categorize_severity(error_count, warning_count)` — maps counts to `none`/`low`/`medium`/`high`/`critical` via documented thresholds.
  - `build_incident_summary(...)` — renders a short human-readable summary.
- **`app/agents/nodes/monitoring_agent.py`** — rewritten as a plain (non-async, non-LLM) function calling `log_parser`. No longer a factory — it has no dependency to close over.
- **`app/agents/state/investigation_state.py`** — replaced the old flat `incident_detected`/`monitoring_summary` fields with a proper `MonitoringResult` model: `incident_detected`, `severity`, `summary`, `error_count`, `warning_count`, `sample_errors`, `sample_warnings`.
- **`app/infrastructure/llm/factory.py`** — `get_llm_provider()` now returns a `_LazyLLMProvider` that defers constructing (and potentially failing on) the real client until the first actual `complete()` call, instead of at FastAPI dependency-resolution time. See "Why this needed fixing" below.
- **`app/api/investigations.py`** — added `POST /api/v1/investigations/upload`, accepting a log file (multipart) with a 5 MiB limit and UTF-8 validation, delegating to the same `run_investigation()` as the existing text endpoint.
- Removed the now-unused `MONITORING_SYSTEM_PROMPT`/`build_monitoring_prompt` from `investigation_prompts.py`.

See `ARCHITECTURE.md` → "Multi-agent orchestration" for the full updated design.

## Why this needed fixing (a real bug found during verification)

While smoke-testing the new upload endpoint, uploading a **clean** log file (no errors — should short-circuit at Monitoring and need no LLM at all) returned `503 LLM_PROVIDER is 'anthropic' but ANTHROPIC_API_KEY is not set`. The cause: FastAPI resolves `Depends(get_llm_provider)` for every request as part of preparing to call the endpoint, regardless of whether the endpoint's logic ends up using it. The old `get_llm_provider()` built (and could fail) the real provider eagerly at that point.

Fixed by making `get_llm_provider()` return a lazy wrapper that only builds/fails on the first real `complete()` call. Re-tested after the fix: the same clean-log upload now returns `200` with a full triage result and zero LLM calls; an incident-containing upload correctly proceeds to Log Analysis and *then* fails with `503`, only when the LLM is genuinely needed.

## How to run it

```bash
cd backend
uv sync
uv run uvicorn app.main:app --app-dir src --reload
```

Text:
```bash
curl -X POST http://localhost:8000/api/v1/investigations \
  -H "Content-Type: application/json" \
  -d '{"logs": "2026-07-31T10:00:00Z INFO checkout-service: request handled in 12ms"}'
```

File upload:
```bash
curl -F "file=@app.log;type=text/plain" http://localhost:8000/api/v1/investigations/upload
```

Neither call needs an LLM API key if the logs contain no errors — Monitoring alone decides that.

## How to test it

```bash
cd backend
uv run pytest -v
uv run ruff check .
```

## Verification performed

- `uv run pytest -v` — 20/20 passing, including:
  - `tests/unit/test_log_parser.py` (9 tests) — pure classification/severity/summary logic, no API key or network needed.
  - `tests/unit/test_investigation_graph.py` — short-circuit path now makes **zero** LLM calls (previously 1, for the old LLM-based monitoring call); full pipeline now makes 4 LLM calls (previously 5).
  - `tests/integration/test_investigations_api.py` — new upload-endpoint tests (success, empty file → 422, non-UTF-8 file → 400) plus two tests added specifically for the lazy-provider fix: a no-incident request succeeds with **no** `dependency_overrides` (the real, unconfigured dependency), and an incident-containing request fails with a clear 503 only once the LLM is actually needed.
- `uv run ruff check .` — clean.
- **Live smoke test**, no API key configured (the honest state of this environment): clean-log file upload → `200` with a real triage result (`severity: "none"`, correct time range extracted); incident-log file upload → `503` with a clear message, only after Monitoring correctly flagged it as needing further analysis.

## Decisions worth calling out

- **Monitoring is rule-based by design, not a stopgap** — see ARCHITECTURE.md for the reasoning (precision, cost, testability without a live LLM).
- **`MonitoringResult` as its own model**, matching the pattern already used for the other three structured agents, rather than leaving ad hoc flat fields on `InvestigationState`.
- **Upload endpoint reuses `run_investigation()` unchanged** — only HTTP-specific concerns (size limit, encoding) live in the router; no business logic duplicated between the text and file entry points.
- **The lazy-provider fix is a correctness fix, not a nice-to-have** — without it, the Monitoring short-circuit's practical benefit (skip the LLM entirely for clean logs) was real at the graph level but unreachable through the actual HTTP API whenever no key was configured.

## What's next

Per the original roadmap: log upload & storage (persisting uploaded files and their investigation results, rather than each request being stateless), Agent Skills, MCP integration, guardrails, evaluation.

# Feature 10: Incident Report Agent — Structured Report + Export

Upgrades the Report Agent from a single free-form "write the whole Markdown report" LLM call into a deterministic six-section template (Summary, Root Cause, Evidence, Confidence, Recommendation, Next Steps) with only the genuinely narrative pieces LLM-authored, and adds `/export` endpoints so a caller can download the finished report as a file rather than parse it out of a JSON blob.

## What changed

- **`app/agents/state/investigation_state.py`** — new `ReportSections` model: just `summary: str` and `next_steps: list[str]`, the only parts of the report that need LLM synthesis.
- **`app/agents/nodes/report_renderer.py`** (new) — pure, dependency-free `render_incident_report_markdown(state, sections)`: assembles the full report from already-validated state (`monitoring`, `log_analysis`, `root_cause`, `recommendations`) plus the LLM's two fields. Also `categorize_confidence_label(score)`, mapping `confidence_score` to High/Medium/Low (thresholds 0.8/0.5).
- **`app/agents/nodes/report_agent.py`** — now asks the LLM for `{"summary": ..., "next_steps": [...]}` JSON (parsed/validated like every other agent's output, raising `AgentOutputError` on malformed responses) instead of free Markdown, then calls the renderer.
- **`app/agents/prompts/investigation_prompts.py`** — `REPORT_SYSTEM_PROMPT` rewritten: explicitly tells the model *not* to restate Root Cause/Evidence/Confidence/Recommendation, since those are rendered separately from data it doesn't need to reproduce.
- **`app/api/investigations.py`** — added `POST /investigations/export` and `POST /investigations/upload/export`, returning the rendered report as a downloadable `.md` file (`text/markdown`, `Content-Disposition: attachment`) instead of the full JSON state. Refactored the upload endpoints' shared file-validation logic into `_read_uploaded_logs()` so both the upload and upload/export endpoints enforce identical size/encoding checks without duplication.

See `ARCHITECTURE.md` → "Multi-agent orchestration" for the full design.

## Why deterministic assembly, not one big LLM-written document

Root Cause, Evidence, Confidence, and Recommendation are already fully validated, structured data by the time Report runs — asking the LLM to write them out again in prose risks it contradicting the data it's supposedly summarizing (e.g. a different confidence percentage than `confidence_score` actually holds, or omitting an anomaly that was actually detected). Rendering them deterministically means the report can never disagree with the pipeline's own findings, and the six required sections are **guaranteed** to appear, in the required order, every time — not "usually, if the model follows instructions." The LLM is used only where it adds real value: writing a coherent executive summary and proposing a follow-up action plan, both of which genuinely require synthesis rather than restating known facts.

## How to run it

Requires `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` (Report is the last of three LLM-backed stages):

```bash
cd backend
uv sync
uv run uvicorn app.main:app --app-dir src --reload
```

Get the full JSON state (report embedded as a string field):
```bash
curl -X POST http://localhost:8000/api/v1/investigations \
  -H "Content-Type: application/json" -d '{"logs": "..."}'
```

Download just the report as a file:
```bash
curl -X POST http://localhost:8000/api/v1/investigations/export \
  -H "Content-Type: application/json" -d '{"logs": "..."}' \
  -o incident-report.md
```

Or from an uploaded log file:
```bash
curl -F "file=@app.log;type=text/plain" \
  http://localhost:8000/api/v1/investigations/upload/export -o incident-report.md
```

## How to test it

```bash
cd backend
uv run pytest -v
uv run ruff check .
```

## Verification performed

- `uv run pytest -v` — 53/53 passing, including:
  - `tests/unit/test_report_renderer.py` (7 new tests, no LLM at all) — all six sections present in the required order; LLM-authored summary/next_steps appear verbatim; Root Cause section reflects the structured hypothesis/pattern/reasoning; Evidence section includes stack traces, repeated failures (with count), and anomalies; Confidence section shows both percentage and label; empty recommendation categories are omitted from the rendered output; confidence-label thresholds at exactly 0.8/0.79/0.5/0.49.
  - `tests/unit/test_investigation_graph.py` — full-pipeline test updated: Report's fake response is now JSON, and the test asserts all six section headings appear in the assembled report, in addition to the LLM-authored next-step text and the confidence percentage/label.
  - `tests/integration/test_investigations_api.py` (3 new tests) — `/investigations/export` returns `200` with `Content-Type: text/markdown` and the correct `Content-Disposition` header; exporting when no incident was detected returns `422`; the upload/export variant works identically over a file.
- `uv run ruff check .` — clean.
- **Direct rendering against realistic data** (stack trace, repeated failure with count, two anomalies, mixed recommendation categories): confirmed the assembled Markdown reads as a coherent, professional document with correct section ordering and content. Caught and fixed a real formatting issue in the process — recommendation categories ran together with no blank line between them (e.g. `**Code fixes:**` bullets immediately followed by `**Configuration changes:**` with no separation); fixed by joining categories with a blank line while still joining bullets within a category with a single newline.

## Decisions worth calling out

- **`ReportSections` is intentionally the smallest schema in the pipeline** — two fields — because everything else already exists as validated data. Resisting the urge to let the LLM regenerate data it doesn't need to touch is the actual point of this feature.
- **Export is a separate endpoint, not a query param or `Accept` header on the existing one** — `/export` returning `Response` with a different `media_type` needs a different `response_model` (or none) than the JSON endpoints; a dedicated route is more explicit in the OpenAPI schema and the code than content-negotiation logic branching inside one handler.
- **No incident → 422 on export, not an empty/broken file** — exporting "nothing" isn't a valid file download; failing clearly is more honest than shipping a mostly-empty `.md`.

## What's next

The full five-agent investigation report is now complete end-to-end (structurally — no live LLM call has been exercised in this environment, still). Per the original roadmap: log upload & storage (persisting investigations, and exporting historical reports rather than only freshly-computed ones), Agent Skills, MCP integration, guardrails, and evaluation remain pending.

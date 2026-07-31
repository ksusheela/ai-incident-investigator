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

Still empty: `domain/`, `guardrails/`, `infrastructure/mcp/client/` — see "Full project layout" below for what each is for and which feature is expected to populate it.

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

## Agent Skills framework

`app/agents/skills/` is a small, self-contained framework for packaging domain expertise as data (Markdown + metadata) instead of hardcoding it into agent prompts, so new expertise can be added without touching agent code. It's the same idea this project's own coding-agent skills use, applied to the incident-investigation pipeline itself.

**The `SKILL.md` format** — YAML front matter, then a Markdown body:

```markdown
---
name: python
version: 1.0.0
description: Guidance for diagnosing Python exceptions and stack traces.
author: AI Incident Investigator
triggers:
  keywords: ["Traceback (most recent call last)", "Error:", "Exception:"]
  patterns: ["Traceback \\(most recent call last\\):", "\\b\\w+(Error|Exception)\\b\\s*:"]
---

# Python

## When this applies
...
## Guidance
...
## Examples
...
```

- **Metadata** (`name`, `version`, `description`, `author`) is parsed into `SkillMetadata` (`app/agents/skills/models.py`); `version` is validated against a strict `MAJOR.MINOR.PATCH` pattern — a malformed version string fails to load rather than being silently accepted.
- **Trigger conditions** (`triggers.keywords`, `triggers.patterns`) determine relevance: a skill matches a log excerpt if *any* keyword appears as a case-insensitive substring, or *any* regex pattern matches. This is deliberately a soft, best-effort match, not an exclusive router — a FastAPI/uvicorn error log matching both the `fastapi` and `python` skills (an ASGI exception is, after all, always backed by a Python traceback) is expected and fine, since matched skills only add optional supplementary context to a prompt rather than gating which agent runs.
- **Examples** are structurally required, not just a convention: `parser.py`'s `parse_skill_markdown()` raises `SkillParseError` if a skill's body has no `## Examples` section, the same "fail loudly on malformed input" stance the rest of this pipeline takes toward LLM output.
- **Versioning**: each skill declares its own version. `SkillLoader` resolves same-`name` conflicts by keeping the higher version and recording the other in `shadowed_skills` (visible, not silently dropped) — there's no multi-version-directory scheme, since a single declared version per skill is all three example skills need; that structure can grow if a real need for coexisting versions ever appears.

**The Skill Loader** (`app/agents/skills/loader.py`): `SkillLoader` discovers every `*/SKILL.md` under `agents/skills/library/`, parses and validates each into a `Skill`, and exposes `.match(text) -> list[Skill]`, `.get(name)`, and `.all_skills()`. `get_skill_loader()` is a `@lru_cache`d FastAPI dependency, the same singleton-on-first-use pattern as `get_settings()` and `get_llm_provider()`. `SkillLoader.from_skills(...)` bypasses disk I/O entirely, constructing a loader from in-memory `Skill` objects — used by tests that need precise control over which skills exist without depending on the bundled library's contents.

**Where it plugs into the pipeline**: Root Cause is the one agent augmented with Skills — `skill_loader.match(state.logs)` runs before its LLM call, and any matched skills' content is appended to the prompt under "Relevant domain expertise" (see `build_root_cause_prompt()` in `investigation_prompts.py`). Root Cause was the natural integration point: it's the first agent that does real interpretive reasoning about the evidence, so injecting targeted domain expertise (Python exception semantics, FastAPI-specific failure shapes) directly improves the quality of its hypothesis. Monitoring and Log Analysis stay skill-free since they're deterministic parsers with nothing for a skill to augment; Recommendation and Report consume Root Cause's output rather than the raw logs directly, so they're one step removed from where trigger matching happens.

**Three bundled example skills** (`agents/skills/library/`): `python` (stack traces, exception categories, third-party-frame heuristics), `fastapi` (ASGI/Starlette/Uvicorn-specific failure patterns, sync-call-in-async-handler symptoms), and `log_analysis` (framework-agnostic baseline heuristics: correlate by time first, a burst outweighs a singleton, the earliest error in a chain is usually the real one). Verified: all three parse and validate cleanly, no name collisions, and the `python` skill's trigger correctly fires on a real Python traceback while none of the three fire on clean logs.

## Filesystem MCP server

`infrastructure/mcp/server/tools.py` builds a real [Model Context Protocol](https://modelcontextprotocol.io) server (the official `mcp` Python SDK, not a bespoke REST shape wearing MCP's name) exposing five tools over confirmed-incident artifacts, mounted into the same FastAPI app at `/mcp/`. See "How this demonstrates MCP concepts" below for what each design choice is illustrating and why.

**What gets persisted, and when**: `infrastructure/filesystem/artifact_store.py`'s `IncidentArtifactStore` writes three files per confirmed incident — `log.txt` (the raw submitted logs), `investigation.json` (the full `InvestigationState`, including its own `incident_id`), and `report.md` (if a report was produced) — under `<incident_artifacts_dir>/<incident_id>/`. `investigation_service.run_investigation()` calls this **only** when `monitoring.incident_detected` is true; clean logs are never persisted, since a filesystem full of "nothing happened" records serves no one. The response's `incident_id` field (new on `InvestigationState`, set by the service layer, not any agent) is what identifies these artifacts afterward.

**Deliberately a filesystem, not a database** — the requirement was literally "Filesystem MCP", and this is also a meaningfully simpler, independent complement to the domain-level persistence (`LogFile`/`Incident` entities, SQL repositories) still deferred to Feature 2: one directory per incident, three flat files, no schema/migrations to manage. Feature 2, when built, may supersede or sit alongside this — it doesn't depend on it.

**Path-traversal protection is explicit, not assumed.** Both `incident_id` and `filename` arrive as plain string tool arguments from a potentially external MCP client — untrusted input, same as an HTTP request body. `_validate_path_component()` rejects any value containing `/`, `\`, `..`, or an empty string before it's used to build a filesystem path, applied everywhere either value reaches `Path` construction. This is deliberate defense-in-depth: worth having even though the store's own path-joining wouldn't literally escape `incident_artifacts_dir` for most inputs, since "most inputs" isn't the bar for code that takes untrusted strings and touches the filesystem.

**Wiring the transport into the existing app**: `MCPServer.streamable_http_app(streamable_http_path="/")` returns a Starlette ASGI app handling requests at its own root, mounted at `app.mount("/mcp", ...)` in `main.py` — so the effective external path is `/mcp/` (a bare `/mcp` 307-redirects there, standard `Mount` behavior, verified live). The Streamable HTTP session manager needs to be running for the whole app lifetime, not just per-request, so `main.py`'s lifespan was extended to `async with mcp_server.session_manager.run(): yield` alongside the existing startup/shutdown logging — one combined lifespan, not two independent ones, since FastAPI only has one lifespan slot per app.

**Verified over the real protocol, not just in-process**: beyond unit tests calling `MCPServer.call_tool()` directly (`tests/unit/test_mcp_server_tools.py`), a live server was started and sent an actual JSON-RPC `initialize` request over HTTP with the real MCP `2025-06-18` protocol envelope — it returned a correct `initialize` response (capabilities, `serverInfo`, `instructions`) via the SSE-framed Streamable HTTP response, confirming the mount, the lifespan-managed session manager, and the SDK's protocol handling all actually work together, not just the tool functions in isolation.

### How this demonstrates Model Context Protocol concepts

- **Server, not client — and that's a real architectural choice, not the only option.** MCP defines two roles: a *server* exposes tools/resources; a *client* consumes them. `infrastructure/mcp/` was scaffolded with both `client/` and `server/` from the start (see "Multi-agent orchestration" history) precisely because a real system might need either or both — an agent that calls out to *other* MCP servers (`client/`, still empty — nothing here needs an external tool yet) versus this app choosing to expose *its own* data to others (`server/`, now built). This feature is entirely the second role.
- **Tools, not a bespoke API shape.** MCP's core primitive for exposing invocable capability is the *tool*: a name, a description, a JSON Schema for its arguments (derived automatically from `read_uploaded_log(incident_id: str) -> str`'s type hints — no schema hand-written), and a structured result. An MCP-aware client (Claude Desktop, an MCP inspector, another agent) can discover these five tools, read their descriptions and schemas, and call them without this project publishing a custom OpenAPI spec or SDK for them — the protocol itself carries that information.
- **A standard transport, decoupled from what runs on top of it.** Streamable HTTP (MCP's current recommended transport) is a generic JSON-RPC-over-HTTP(+SSE) envelope; the *same* `MCPServer` instance could instead speak stdio (`run_stdio_async()`, the transport Claude Desktop uses for local tool integrations) with zero changes to the tool definitions. Demonstrated here via HTTP because it's the transport that fits naturally into an existing FastAPI service; the tool logic itself is transport-agnostic, which is the point of MCP standardizing the transport layer separately from the capability layer.
- **Structured content, not string-wrangling.** `list_incidents`/`list_exported_files` return typed Python data (`list[dict]`, built from dataclasses); the SDK surfaces it both as human-readable `content` (one text block per item) and machine-readable `structured_content` (the original structure, JSON-Schema-validated) — a client can consume whichever it needs, without the tool author choosing one representation and forcing the other.
- **Protocol-level error semantics, not ad hoc exception messages.** A tool raising `ValueError` (e.g. an unknown `incident_id`, a path-traversal attempt) is translated by the SDK into a protocol-level tool error a client can detect and handle programmatically (`isError`/`ToolError`), the MCP equivalent of this project's existing "never let malformed output pass silently" stance for LLM responses — applied here to tool-call inputs instead.
- **Instructions as a resource description, not a docstring only for humans.** `SERVER_INSTRUCTIONS` is passed to `MCPServer(..., instructions=...)` and surfaced in the `initialize` response itself (confirmed in the live smoke test) — it's protocol-visible metadata an MCP client can show a user or feed to its own model, not just a code comment.

## Evaluation module

`app/evaluation/` measures every confirmed incident's investigation against four metrics — response time, confidence, root-cause quality, recommendation quality — and the frontend's Dashboard displays the aggregate across all of them (`GET /api/v1/evaluations/summary`).

**Response time** is wall-clock time around the LangGraph invocation (`time.perf_counter()` in `investigation_service.run_investigation()`), covering however much of the pipeline actually ran — just Monitoring+Log Analysis for logs with no incident (though those aren't evaluated at all, see below), or the full five-agent pipeline for a confirmed one.

**Confidence** is not a new computation — it's `root_cause.confidence_score`, already produced (and already bounded `[0.0, 1.0]`) by the Root Cause Agent since Feature 8. The evaluation module's job here is purely to capture and aggregate a number that already exists, not derive a new one.

**Root-cause quality and recommendation quality are both rule-based rubrics** (`app/evaluation/metrics.py`), not an LLM-as-judge call — consistent with this project's established pattern: Monitoring and Log Analysis are rule-based because their tasks are mechanical, and this is the same reasoning applied to evaluation itself. A `QualityScore` is the fraction of a small set of named `QualityCheck`s that passed:

- Root cause (4 checks): reasoning is detailed (≥15 words), reasoning references concrete evidence-related terms (error/exception/timeout/trace/etc.), `contributing_factors` is non-empty, `matched_pattern` is not `null`.
- Recommendation (3 checks): at least one recommendation exists, every rationale is detailed (≥6 words), recommendations span more than one category.

Each `QualityCheck` carries its own `detail` string explaining why it passed or failed — the same "explain the score, don't just report a number" instinct behind `RootCauseResult.reasoning` and `Recommendation.rationale` applies to evaluating those fields too. **This rubric measures presence and specificity, not truth** — it can't tell you whether a hypothesis is actually *correct*, only whether it looks like a well-formed one. Genuinely judging correctness would need human review or a real LLM-judge call (what DeepEval's metrics do); that's a heavier, costlier evaluation path this project can add later, and isn't verifiable in this environment anyway with no LLM key configured. A rubric that scores the same input identically every time is also the only kind of evaluation this feature can prove actually works without a live model.

**Only confirmed incidents are evaluated**, the same gate as artifact persistence (`monitoring.incident_detected`) — there's no root cause or recommendation to score for clean logs, and evaluating "nothing happened" would just double-count what Monitoring already reports. `evaluate_investigation()` is called immediately after `IncidentArtifactStore.save_incident()` assigns the `incident_id`, and its result is persisted as a fourth file, `evaluation.json`, alongside `log.txt`/`investigation.json`/`report.md`.

**Aggregation, not per-incident inspection, is the dashboard's job.** `summarize_evaluations()` averages `response_time_seconds`, `confidence_score`, and both quality scores across every stored `evaluation.json` (`IncidentArtifactStore.list_evaluations()`, skipping any incident that predates this feature and has none). With zero evaluated incidents, every average is `null`, not `0` — a zero would look like a real, poor score rather than "no data yet." `GET /api/v1/evaluations/summary` needs no LLM dependency at all — it only reads already-computed files — verified live: an empty environment returns all-`null` averages, and after a real (fake-LLM-backed, since no API key is configured here) investigation, returns `evaluated_count: 1` with an exact-matching `avg_confidence_score` and correctly fractional quality scores (2 of 3 recommendation checks passing rendered as `0.667`).

**On the Dashboard**, `EvaluationSummaryCard` (`frontend/src/pages/DashboardPage.tsx`, alongside the existing `SystemStatusCard`/`RecentIncidentsCard`) follows the same real-API-call-with-honest-states pattern established since the frontend was built: loading spinner, error alert on failure, an explicit empty state when `evaluated_count` is 0, and the five metrics rendered as percentages/seconds only once there's real data. Unlike `RecentIncidentsCard` (which still calls a backend endpoint that doesn't exist), this card's backend endpoint is real and working today — verified both by a live curl round-trip and by frontend component tests covering all three states with a mocked service response.

## Frontend dashboard: real incident/evaluation REST endpoints, page restructuring, and charts

The frontend was rebuilt from a 4-page skeleton with two permanently-erroring pages into a 5-page dashboard (Dashboard, Incident Analysis, Reports, Evaluation, Settings) backed entirely by real endpoints — no page renders mock or placeholder data.

**New REST endpoints, and why they exist alongside the Filesystem MCP server.** `app/api/incidents.py` adds `GET /incidents` (wraps `IncidentArtifactStore.list_incidents()`) and `GET /incidents/{incident_id}/report` (wraps `read_report()`, 404 via `ExportedFileNotFoundError`/`ValueError`); `app/api/evaluations.py` gains `GET /evaluations` (every stored `EvaluationResult`, most recently evaluated first — `list_evaluations()` was extended to sort by `evaluated_at`, matching `list_incidents()`'s existing "most recent first" contract) and `GET /evaluations/{incident_id}`. This is a deliberate reversal of Feature 12's choice to expose `list_incidents`/report-reading **only** through MCP: that was the right call for an AI-agent-facing capability, but MCP's JSON-RPC/Streamable-HTTP transport isn't what a browser's `fetch()` should speak for routine page rendering — a real dashboard needs plain REST. The two surfaces now coexist deliberately: MCP for AI-agent/tool clients, REST for this frontend, both reading the same `IncidentArtifactStore` underneath.

**Route ordering matters for `/evaluations`.** FastAPI/Starlette match routes in registration order; `/evaluations/summary` (a literal path) is registered before `/evaluations/{incident_id}` (a path param) specifically so a request for the aggregate summary can't be swallowed by the single-incident route.

**Page restructuring:**

- **Incident Analysis** (`pages/IncidentAnalysisPage.tsx`, route `/incident-analysis`) replaces the old `IncidentsPage`, which only ever rendered a permanent "not available yet" error — there was no backend list endpoint when it was built. It's now a genuine two-part workspace: a form that submits raw log text to `POST /investigations` and renders the full pipeline output (Monitoring summary, Log Analysis findings, Root Cause with a confidence progress bar, grouped Recommendations, and the rendered report with a client-side `Blob`-based ".md" download — no extra round-trip to `/export` needed, since the report text is already in the response), plus a browser over past incidents.
- **Reports** (`pages/ReportsPage.tsx`) is now a real report browser instead of a page permanently erroring against a nonexistent `/reports` endpoint: list confirmed incidents, click "View report" to fetch and render one's persisted Markdown via the new `GET /incidents/{id}/report`.
- **`components/incidents/IncidentReportBrowser.tsx`** is the shared implementation behind both of the above — list incidents, fetch a report on demand, show it inline. Extracting it was justified by actual duplication (both pages need identical behavior), not speculative reuse.
- **Evaluation** (`pages/EvaluationPage.tsx`, route `/evaluation`) is a new dedicated page: the aggregate summary (same numbers as the Dashboard's card) plus a bar chart of the three percentage metrics, and a full table of every individual `EvaluationResult` via the new `GET /evaluations` list endpoint — previously there was no way to see anything but the aggregate.
- **Dashboard** (`pages/DashboardPage.tsx`) keeps its three original cards — `RecentIncidentsCard` now renders real data instead of a permanent error, since `getIncidents()` calls a real endpoint — and gains a full-width `SeverityDistributionCard` chart.

**Charts, built per the "dataviz" skill's procedure, not by eyeballing colors.** Two real charts exist, both single-series bar charts (`components/charts/BarChart.tsx`, hand-rolled inline SVG — no charting library dependency for two simple bar charts):

- *Form*: both charts answer "compare magnitude across a handful of categories" — the skill's table maps that job straight to a bar/column chart, not a pie or dual-axis chart.
- *Color*: the Dashboard's severity distribution uses the skill's **status palette** (good/warning/serious/critical, plus a neutral for "none") rather than arbitrary categorical hues, because severity genuinely *is* a status field, not five unrelated series — the same status colors also back `SeverityBadge`, so a severity reads identically everywhere it appears. The Evaluation page's chart (confidence / root-cause quality / recommendation quality) is a single series (one score, three categories), so it uses the skill's single **sequential** hue rather than distinct categorical colors, per the "single series needs no legend, identity comes from the axis label" rule.
- *Values are adopted verbatim from the skill's reference palette* (`references/palette.md`), which ships pre-validated against its six accessibility checks (CVD ΔE, normal-vision floor, contrast) for both light and dark chart surfaces — no custom hues were invented, so no new validator run was needed. Status colors are intentionally **not** re-themed for dark mode (the palette documents them as fixed across modes); the chart chrome (baseline, axis/value label ink, the sequential hue) does swap via `[data-bs-theme="dark"]`, the same attribute `ThemeProvider` already drives.
- *Marks*: bars are capped at 24px thick, rounded on the top corners only (square at the baseline, via a hand-written SVG path rather than a plain rounded `<rect>`), grow from a shared hairline baseline, and carry a direct value label at the tip plus a category label below — every value is readable without hovering, which is why no separate table view was added underneath either chart. A lightweight per-bar hover/focus tooltip (a text line above the chart, not a floating popup) is included per the skill's "ship the hover layer by default" rule, even though direct labels already make it non-load-bearing.

**Verification**: 135 backend tests passing (9 new, covering the new endpoints' happy paths, 404s, and the `list_evaluations()` sort), `ruff check` clean; 16 frontend tests passing (8 new — `BarChart`'s direct labels and hover tooltip, `IncidentAnalysisPage`'s submit-and-render flow and error state, `EvaluationPage`'s empty/populated states, `DashboardPage`'s real incident rendering and severity chart), `eslint`/`tsc -b`/`vite build` all clean. The new endpoints were also exercised live end-to-end: a real (fake-LLM-backed) investigation was persisted, then `GET /incidents`, `GET /incidents/{id}/report`, `GET /evaluations`, `GET /evaluations/{id}`, and both 404 paths were confirmed against it with matching real data. Full in-browser visual verification (actually clicking through the running app) was **not** performed in this environment — no browser-automation tool was available — so the claim above is scoped to what the automated test suites and live API calls actually confirm.

## Pre-release review: CORS fix, duplication removal, and hardening

A full-project review (backend + frontend audits, Docker verification, live integration testing) found and fixed a handful of real issues before the first release. This section records what changed and why; `docs/features/15-pre-release-review.md` has the full write-up.

**The CORS bug — the headline finding.** No `CORSMiddleware` existed anywhere in `main.py`, and `vite.config.ts` has no dev proxy. Every frontend `fetch()` call to the backend was therefore a genuine cross-origin request from the browser's perspective, silently blocked by the same-origin policy — even though every prior "live verification" in this project's history used `curl` or `httpx.AsyncClient`, neither of which enforces CORS (only browsers do), so the bug went undetected through 14 prior features. Fixed via `Settings.cors_allowed_origins` (comma-separated, defaulting to `http://localhost:5173` — the frontend's origin in both dev and prod Compose configs) and `CORSMiddleware` added in `create_app()`, restricted to `GET`/`POST` (the only methods this API uses) with `allow_credentials=False` (no cookie-based auth exists to protect). Verified three ways: `tests/integration/test_cors.py` (allowed origin gets the header, a disallowed one doesn't, an OPTIONS preflight is handled), and a real `docker compose up` with an actual `curl -H "Origin: http://localhost:5173"` preflight against the running container, returning genuine `Access-Control-Allow-Origin`/`Access-Control-Allow-Methods` headers.

**Duplication removed, backend:**

- `app/api/common.py`'s `translate_to_404()` (a context manager) replaces an identical `try/except (ExportedFileNotFoundError, ValueError): raise HTTPException(404, ...)` block that had been copy-pasted between `api/incidents.py` and `api/evaluations.py`.
- `infrastructure/mcp/server/tools.py`'s `_call_store()` helper replaces the same three-line "run off-thread, translate lookup errors to `ValueError`" shape that appeared four times across the five MCP tools.

**Duplication removed, frontend:**

- `components/common/AsyncSection.tsx` replaces the loading/error/empty/success four-way conditional that had been copy-pasted seven times across `DashboardPage`, `EvaluationPage`, and `IncidentReportBrowser` — each call site now passes its `AsyncState`, an empty-check, and a render function.
- `utils/format.ts`'s `formatPercent`/`formatSeconds` replace byte-identical functions that existed independently in both `DashboardPage.tsx` and `EvaluationPage.tsx`.
- `components/incidents/ReportViewer.tsx` replaces an identical `<pre>` Markdown-display block duplicated between `IncidentAnalysisPage` and `IncidentReportBrowser`.
- `DashboardPage`'s `SeverityDistributionCard` was recomputing `severityDistribution()` twice per render (once for the chart data, once for `maxValue`); now computed once into a local constant.

**A real request-size gap, fixed**: `POST /investigations`' `InvestigationRequest.logs` had no `max_length`, while `POST /investigations/upload` enforced a 5 MiB cap on the same underlying data — despite the module's own docstring claiming both endpoints are equivalent. Both now share the same limit, closing a cost/DoS gap on the path that feeds directly into LLM prompts uncapped.

**Known gaps, documented rather than half-fixed.** Two findings were deliberately **not** code-fixed, because a partial fix would be worse than an honest limitation:

- **No authentication anywhere** — not the REST API, not the Filesystem MCP mount (which includes a destructive `delete_exported_file` tool). Bolting an optional, easy-to-forget-to-configure auth check onto just one router would create false confidence without actually being a real access-control system. Documented in `README.md` → "Known limitations" and `RELEASE_CHECKLIST.md` as a hard requirement before any public deployment, rather than built here.
- **`IncidentArtifactStore.list_incidents()`/`list_evaluations()` scan and JSON-parse every incident directory on every call.** Fine at the scale this project targets (a demo/local dataset), but it's an O(n) full-directory-walk with no index, and will degrade as incidents accumulate. The real fix is the already-deferred domain-level persistence (a real database with an index), not a bespoke caching layer bolted onto a filesystem store meant to stay simple.

**Test coverage added**: `tests/unit/test_config.py` (Settings/`cors_origins` parsing, including multi-origin, whitespace, and blank-entry handling — previously untested even though a parsing bug here would silently break every frontend request), and an integration test proving `AgentOutputError` actually reaches the client as a 502 through the real API (previously only unit-tested by calling the agent function directly, never exercised through `main.py`'s exception handler). Frontend gained direct tests for `apiClient` (all four methods, plus the `ApiError` path — previously only ever exercised indirectly through mocked service modules), `formatIncidentTimestamp`, `format.ts`, `SeverityBadge`, `IncidentReportBrowser`/`ReportsPage` (list → view report → error, none of which had a dedicated test before), and an `App.test.tsx` that actually navigates across all 5 routes plus the 404 fallback — the first test in this project that exercises routing end-to-end rather than one page in isolation.

**Docker, verified for real, not just `config` validation**: both Compose files were built and run (`docker compose up`, `docker compose -f docker-compose.prod.yml up`), not just `docker compose config`. Confirmed live: both services reach a healthy state, the CORS preflight above returns real headers, production's `/docs` is genuinely `404`, and the frontend's SPA fallback correctly serves `index.html` for a client-side route like `/incident-analysis` instead of nginx 404ing it.

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

**API service layer**: `services/apiClient.ts` is a thin typed `fetch` wrapper (base URL from `config.ts`, throws a typed `ApiError` on non-2xx; also exposes `post()` and a `getText()` for the Markdown report endpoint, which isn't JSON). Per-resource modules (`healthService.ts`, `incidentService.ts`, `investigationService.ts`, `evaluationService.ts`) each expose one typed function per endpoint. `types/` mirrors the backend's Pydantic schemas by hand (e.g. `HealthStatus` matches `HealthResponse`, `InvestigationState` matches the graph's state, field-for-field) since there's no shared schema codegen yet.

**Every page now calls a real, working endpoint** — see "Frontend dashboard" below for the REST endpoints added specifically to make this true, and what replaced the two pages that used to permanently error against endpoints that didn't exist.

**Settings page** is fully functional today, not a placeholder: it drives a real light/dark theme toggle via Bootstrap 5.3's native `data-bs-theme` color modes (`store/themeContext.ts` + `store/ThemeProvider.tsx`), persisted to `localStorage`, defaulting to the OS's `prefers-color-scheme`. It also displays the resolved `VITE_API_BASE_URL` for debugging.

**Environment configuration**: `src/config.ts` mirrors the backend's `Settings` pattern — one module reads `import.meta.env`, validates it (throws if `VITE_API_BASE_URL` is missing), and everything else imports the parsed `config` object rather than reading `import.meta.env` directly. Vite env vars are compile-time, not runtime, which matters for Docker (see below).

**Testing**: Vitest + React Testing Library, mirroring the backend's pytest setup. `tests/setup.ts` adds jest-dom matchers and a `matchMedia` polyfill (jsdom doesn't implement it, and `ThemeProvider` needs it for system-theme detection). Tests cover `useAsync`'s loading/success/error transitions, `Sidebar`'s nav links and active-route highlighting (now 5 pages), `ThemeProvider`'s theme toggle + persistence, `DashboardPage`'s evaluation summary and (since the dashboard rebuild) its real incident list and severity chart, `BarChart`'s direct labels and hover tooltip, `EvaluationPage`'s empty/populated states, and `IncidentAnalysisPage`'s submit-and-render flow and error state — all with service modules mocked via `vi.mock` rather than hitting a real (or absent) backend.

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
│   │   ├── api/                       [in use] HTTP layer: routers, request/response schemas (health, investigations, evaluations, incidents); `common.py` for genuine cross-router duplication only
│   │   ├── domain/                    [Feature 2] Framework-free business layer
│   │   │   ├── entities/               Core business objects (e.g. LogFile, Incident) — plain Python/Pydantic, no ORM/HTTP imports
│   │   │   ├── repositories/            Abstract repository interfaces (ports) that infrastructure/ implements
│   │   │   └── exceptions/               Domain-level error types, independent of HTTP status codes
│   │   ├── services/                  [in use] `investigation_service.py` — builds the graph, runs it, returns the final state
│   │   ├── infrastructure/            Concrete adapters implementing domain/external interfaces
│   │   │   ├── database/                [in use] `base.py` (declarative Base); ORM models + repository implementations land in Feature 2
│   │   │   │   └── migrations/           [in use] Alembic (async), wired to Base.metadata + Settings; no versions/ yet — first real migration lands with Feature 2's models
│   │   │   ├── llm/                     [in use] `LLMProvider` Protocol + `AnthropicProvider`/`GeminiProvider` adapters + cached factory
│   │   │   ├── filesystem/              [in use] `IncidentArtifactStore` — confirmed-incident artifacts on disk (including `evaluation.json`); exposed both by the Filesystem MCP server and by `api/incidents.py`/`api/evaluations.py`'s REST endpoints
│   │   │   └── mcp/                     Model Context Protocol integration
│   │   │       ├── client/               Consumes external MCP tool servers from within agents (still empty — nothing needs an external tool yet)
│   │   │       └── server/               [in use] `tools.py` — the Filesystem MCP server, 5 tools over `IncidentArtifactStore`, mounted at `/mcp`
│   │   ├── agents/                    [in use] Multi-agent architecture, orchestrated with LangGraph — see "Multi-agent orchestration" above
│   │   │   ├── graphs/                  [in use] `investigation_graph.py` — the compiled `StateGraph`
│   │   │   ├── nodes/                   [in use] `monitoring_agent.py`+`log_parser.py` and `log_analysis_agent.py`+`log_analyzer.py` (both rule-based); `failure_patterns.py` (Root Cause's catalog); `report_renderer.py` (deterministic template); a factory per LLM agent: root_cause, recommendation, report
│   │   │   ├── state/                   [in use] `InvestigationState` + per-agent result models
│   │   │   ├── prompts/                 [in use] System/user prompt builders, one set per agent
│   │   │   └── skills/                  [in use] Agent Skills framework — `models.py`/`parser.py`/`loader.py` + `library/{python,fastapi,log_analysis}/SKILL.md`; matched into Root Cause's prompt
│   │   ├── guardrails/                [Feature 8] Input/output validation and safety checks wrapping LLM calls
│   │   └── evaluation/                [in use] `models.py`/`metrics.py`/`evaluator.py` — response time, confidence, and rule-based quality rubrics for confirmed incidents
│   ├── tests/
│   │   ├── unit/                       [in use] `test_investigation_graph.py` — graph/node behavior via a fake LLM provider
│   │   ├── integration/                 [in use] `test_investigations_api.py` — the real HTTP layer, LLM dependency overridden
│   │   └── e2e/                          Full agent-pipeline runs against a running app instance
│   ├── Dockerfile                     [in use] multi-stage: shared `base` -> `development` (uv sync w/ dev deps, --reload) / `production` (--no-dev, no reload)
│   └── pyproject.toml                 [Feature 1, in use]
├── frontend/                          [in use] React + TypeScript + Bootstrap 5 client (Vite)
│   ├── public/                         Static assets served as-is (currently empty)
│   ├── src/
│   │   ├── components/                  [in use] `layout/` (AppLayout, Sidebar, Topbar, HealthBadge), `common/` (LoadingSpinner, ErrorAlert, EmptyState, SeverityBadge, `AsyncSection` — the shared loading/error/empty/success wrapper), `charts/` (BarChart), `incidents/` (IncidentReportBrowser + ReportViewer, shared by Reports + Incident Analysis)
│   │   ├── pages/                        [in use] DashboardPage, IncidentAnalysisPage, ReportsPage, EvaluationPage, SettingsPage, NotFoundPage
│   │   ├── features/                      Feature-sliced modules, for when a page outgrows components/+pages/ (empty — not yet warranted)
│   │   ├── services/                      [in use] apiClient + one module per resource (health, incident, investigation, evaluation)
│   │   ├── hooks/                          [in use] `useAsync` — shared loading/success/error state for API calls
│   │   ├── types/                          [in use] HealthStatus, IncidentSummary, InvestigationState, EvaluationResult/EvaluationSummary — all mirror real, working backend endpoints
│   │   ├── store/                           [in use] ThemeProvider + theme context (light/dark, Bootstrap 5.3 color modes)
│   │   ├── styles/                           [in use] `custom.css` — Bootstrap utility overrides + the dataviz chart/status color roles
│   │   └── utils/                             [in use] `formatIncidentTimestamp` (incident-id timestamp prefix), `format.ts` (`formatPercent`/`formatSeconds`, shared by Dashboard + Evaluation)
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
- **MCP lives under `infrastructure/mcp/`, split into `client/` and `server/`.** MCP is fundamentally an infrastructure integration (a protocol adapter), consistent with how `infrastructure/` already documents LLM provider adapters. `client/` is what agents use to call *other* MCP tool servers (still empty — nothing needs an external tool yet); `server/` is this app choosing to *expose* its own incident data as MCP tools to other systems — two distinct directions of the same protocol, worth keeping visually separate. See "Filesystem MCP server" below for the `server/` side, now built.
- **The artifact store lives in `infrastructure/filesystem/`, separate from `infrastructure/mcp/server/`.** The filesystem storage mechanism (`IncidentArtifactStore`: save/read/list/delete files) and the MCP protocol wiring (`tools.py`: turn those methods into MCP tool calls) are different concerns — the store has no idea MCP exists, and could be reused by a REST endpoint without importing anything MCP-flavored. `services/investigation_service.py` already does exactly that.
- **`services/` is a separate top-level layer, not folded into `domain/`.** Domain stays framework-free and dependency-free; `services/` is where orchestration across domain + infrastructure + agents happens and is where FastAPI routers' `Depends()` chains terminate.

## Deferred by design (not yet built)

Every folder in the layout above marked with a feature number is empty until that feature lands. Building real logic into them now, before there's an agent or endpoint that needs it, would be exactly the kind of speculative abstraction this project's rules avoid — the folders exist now only because scaffolding the map was explicitly requested independently of implementation.

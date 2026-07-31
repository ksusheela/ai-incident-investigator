# Feature 8: Root Cause Analysis Agent

Upgrades the Root Cause Agent's output from a loose `{hypothesis, confidence: str, contributing_factors}` shape into a richer, more rigorous structured result, and adds a known-failure-pattern catalog to match evidence against — while deliberately staying LLM-backed, unlike Monitoring and Log Analysis.

## What changed

- **`app/agents/nodes/failure_patterns.py`** (new) — a curated catalog of 8 common production-incident failure patterns (`connection_pool_exhaustion`, `cascading_timeout`, `resource_exhaustion`, `null_reference`, `deadlock_or_contention`, `configuration_error`, `dependency_outage`, `traffic_spike`), each with a name and description, rendered into the Root Cause Agent's system prompt.
- **`app/agents/state/investigation_state.py`** — `RootCauseResult` restructured:
  - `confidence: str` → `confidence_score: float` constrained to `[0.0, 1.0]` via a Pydantic `Field(ge=0.0, le=1.0)`.
  - Added `matched_pattern: str | None` — the name of the catalog entry that best matches the evidence, or `null` if none clearly apply.
  - Added `reasoning: str` — a required, separate field explaining *why* the evidence supports the hypothesis (distinct from `hypothesis` itself, which is just the claim).
  - Kept `contributing_factors: list[str]`.
- **`app/agents/nodes/root_cause_agent.py`** — after parsing/validating the JSON response, additionally checks that `matched_pattern` (if not `null`) is one of the catalog's known names, raising `AgentOutputError` if not — a hallucinated pattern name is exactly the kind of malformed output the rest of the pipeline already refuses to accept silently.
- **`app/agents/prompts/investigation_prompts.py`** — `ROOT_CAUSE_SYSTEM_PROMPT` now renders the failure-pattern catalog and instructs the model to explain its reasoning explicitly; `build_recommendation_prompt` updated to read the new field names.

See `ARCHITECTURE.md` → "Multi-agent orchestration" for the full design.

## Why this stays LLM-backed (unlike Monitoring/Log Analysis)

Analyzing evidence and judging which explanation best fits it — and explaining why — is genuine inference, not mechanical parsing. That's the same line drawn in Features 6 and 7: rule-based where the task is precise counting/extraction, LLM-backed where it's judgment. The catalog doesn't change that — it gives the LLM a menu of well-known shapes to check evidence against (and an explicit "none of these" option), but it's still the LLM doing the matching and explaining, not a rule engine.

## How to run it

Requires `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` (Monitoring and Log Analysis run for free; Root Cause is the first agent in the pipeline that actually needs the LLM):

```bash
cd backend
uv sync
uv run uvicorn app.main:app --app-dir src --reload
```

```bash
curl -X POST http://localhost:8000/api/v1/investigations \
  -H "Content-Type: application/json" \
  -d '{"logs": "..."}'
```

## How to test it

```bash
cd backend
uv run pytest -v
uv run ruff check .
```

## Verification performed

- `uv run pytest -v` — 38/38 passing, including:
  - `tests/unit/test_failure_patterns.py` (4 tests) — catalog well-formedness (non-empty, unique names, non-empty descriptions, every name appears in the rendered prompt text).
  - `tests/unit/test_root_cause_agent.py` (5 new tests, agent tested in isolation via a fake LLM provider) — accepts a valid catalog match, accepts `null` for a novel failure, **rejects** a pattern name outside the catalog, **rejects** an out-of-range confidence score, **rejects** a response missing the required `reasoning` field.
  - `tests/unit/test_investigation_graph.py` — full-pipeline test updated to the new `RootCauseResult` shape.
- `uv run ruff check .` — clean.
- **Live smoke test**: `POST /api/v1/investigations` with real incident logs correctly ran both deterministic agents and failed with a clear `503` once Root Cause needed the (unconfigured) LLM. Fetched `/openapi.json` and confirmed `RootCauseResult`'s schema correctly reflects `confidence_score`'s `minimum: 0.0, maximum: 1.0` constraint and `matched_pattern`'s nullable type — the API contract, not just the Python model, enforces this.
- **Not verified**: an actual live call to Claude or Gemini producing a real root-cause hypothesis — no API key is configured in this environment, so the prompt's real-world effectiveness (does the model actually pick sensible `matched_pattern` values, does its `reasoning` hold up) hasn't been observed, only the validation logic around whatever a model *would* return.

## Decisions worth calling out

- **The pattern catalog lives in code, not a database or config file** — it's small, static, and versioned with the prompt that references it; no persistence needed for 8 curated entries.
- **An unknown `matched_pattern` is a hard error, not silently coerced to `null`** — consistent with this pipeline's existing stance that malformed LLM output should fail loudly (`AgentOutputError` → 502), not be quietly papered over.
- **`confidence_score` is a float with real bounds enforced by Pydantic**, not a free-form string — a small change, but it's the difference between "high" (meaningless outside the model's own head) and a value other code (or a future evaluation harness) can actually threshold on.

## What's next

Per the original roadmap: Recommendation and Report remain LLM-backed and still need a real API key to exercise end-to-end. Log upload & storage, Agent Skills, MCP, guardrails, and evaluation (which could eventually score `confidence_score` calibration against ground truth) remain pending.

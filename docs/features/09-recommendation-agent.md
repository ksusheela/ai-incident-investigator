# Feature 9: Recommendation Agent — Categorized Fixes with Rationale

Upgrades the Recommendation Agent's output from a generic `{immediate_actions, long_term_fixes}` shape (two arbitrary urgency buckets of bare strings) into three explicit fix categories, each item carrying its own explanation. Stays LLM-backed, like Root Cause — deciding what to fix and why is judgment, not parsing.

## What changed

- **`app/agents/state/investigation_state.py`**:
  - New `Recommendation` model: `description: str` + `rationale: str` — every suggested fix now carries its own explicit explanation, not just a bare action string.
  - `RecommendationResult` restructured: `immediate_actions`/`long_term_fixes` → `code_fixes: list[Recommendation]`, `configuration_changes: list[Recommendation]`, `database_improvements: list[Recommendation]`.
- **`app/agents/prompts/investigation_prompts.py`** — `RECOMMENDATION_SYSTEM_PROMPT` rewritten to define the three categories precisely (code vs. config vs. database), instruct the model to leave a category empty rather than padding it with generic advice, and require each `rationale` to explain *why* that specific fix addresses the root cause.
- **`app/agents/nodes/recommendation_agent.py`** — after parsing/validating, additionally rejects a response where all three categories are empty: a confirmed root cause with zero actionable recommendations is itself a malformed response, not a valid "nothing to do here."

See `ARCHITECTURE.md` → "Multi-agent orchestration" for the full design.

## How to run it

Requires `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` (Recommendation is the second LLM-backed stage, after Root Cause):

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

- `uv run pytest -v` — 43/43 passing, including:
  - `tests/unit/test_recommendation_agent.py` (5 new tests, agent tested in isolation via a fake LLM provider) — accepts recommendations spread across all three categories, accepts some categories empty (only configuration_changes populated), **rejects** all three categories empty, **rejects** a recommendation missing `rationale`, rejects unparseable output.
  - `tests/unit/test_investigation_graph.py` — full-pipeline test updated to the new categorized shape.
- `uv run ruff check .` — clean.
- **Live smoke test**: `POST /api/v1/investigations` with real incident logs correctly reached the LLM-backed stages and failed with a clear `503` (no key configured, as in every prior feature's honest verification in this environment). Fetched `/openapi.json` and confirmed `RecommendationResult`'s schema correctly shows three required array properties, each referencing the `Recommendation` schema (`description` + `rationale`, both required) — the API contract enforces the shape, not just the Python model.
- **Not verified**: an actual live call producing real recommendations — no API key is configured in this environment, so whether a real model's category assignments and rationales are actually *good* hasn't been observed, only the validation logic around whatever it returns.

## Decisions worth calling out

- **Three fixed categories, not a free-form list** — matches the explicit ask (code/configuration/database) rather than the previous generic urgency split, which didn't map to anything actionable for a team deciding who picks up the fix.
- **Empty categories are valid; all-empty is not** — mirrors real incident response, where not every fix touches every layer, while still guaranteeing the agent produces *something* actionable for a confirmed root cause.
- **`rationale` lives on every individual recommendation**, not once at the top level — different fixes in the same response can (and often do) address different contributing factors, so a single shared explanation wouldn't be accurate.

## What's next

Per the original roadmap: Report remains LLM-backed and still needs a real API key to exercise end-to-end. Log upload & storage, Agent Skills, MCP, guardrails, and evaluation remain pending.

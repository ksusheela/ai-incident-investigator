# Feature 7: Log Analysis Agent — Deterministic Deep Parsing

Upgrades the Log Analysis Agent from an LLM-prompted "extract findings as JSON" call into a rule-based deep-parsing engine, consistent with the Monitoring Agent's redesign in Feature 6.

## What changed

- **`app/agents/nodes/log_analyzer.py`** (new) — pure, dependency-free functions:
  - `extract_stack_traces(logs)` — parses standard CPython tracebacks (`Traceback (most recent call last):` header, `File "...", line N, in <func>` frames, final `ExceptionType: message` line) into structured `StackTrace` records.
  - `identify_repeated_failures(error_lines)` — groups error lines by a normalized signature (timestamp stripped, digits collapsed to `#`) and reports groups seen 2+ times as `RepeatedFailure`s, with occurrence count and first/last-seen timestamps.
  - `detect_anomalies(error_lines)` — two concrete rule-based checks: an isolated CRITICAL/FATAL event (not part of any repeated group), and a burst of 5+ errors within a 60-second window.
  - `extract_affected_components(logs)` — pulls out service/component names mentioned alongside a level marker (e.g. `ERROR checkout-service: ...`).
- **`app/agents/nodes/log_analysis_agent.py`** — rewritten as a plain (non-LLM) function calling `log_analyzer`, mirroring `monitoring_agent.py`'s shape.
- **`app/agents/state/investigation_state.py`** — `LogAnalysisResult` restructured: dropped the free-text `key_errors`/`patterns` fields in favor of `stack_traces: list[StackTrace]`, `repeated_failures: list[RepeatedFailure]`, and `anomalies: list[str]`, alongside the existing `affected_components`/`time_range`.
- **`app/agents/prompts/investigation_prompts.py`** — removed the now-unused `LOG_ANALYSIS_SYSTEM_PROMPT`; `build_root_cause_prompt` updated to consume the new structured fields instead of the old free-text ones.
- **`app/agents/graphs/investigation_graph.py`** — Log Analysis wired in directly as a plain function (no longer a factory needing `llm`).
- **`app/agents/nodes/log_parser.py`** — exposed `extract_leading_timestamp()` as a shared public helper so `log_analyzer.py` doesn't duplicate the timestamp regex.

See `ARCHITECTURE.md` → "Multi-agent orchestration" for the full updated design and why both the first two agents are rule-based.

## Why this needed fixing (a real bug found during verification)

While smoke-testing `extract_affected_components` against realistic logs, a log line containing **"500 Internal Server Error"** caused the parser to extract a bogus component: the word "Error" (mixed case) matched the component-extraction regex's level-marker alternation case-insensitively, and the parser then grabbed the *next line's leading timestamp* as if it were a component name, because the regex greedily matched across the newline to the next `:`.

Fixed by making the component-extraction regex case-sensitive: a structured log level marker is conventionally all-uppercase (`ERROR`, `WARN`), while a level-like word embedded in a message ("Internal Server Error") is normally mixed case. This is a different precision/recall trade-off than `log_parser.py`'s error/warning *detection*, which intentionally stays case-insensitive since it only needs to flag a line as error-level, not extract a token immediately after it. A regression test locks this in.

## How to run it

```bash
cd backend
uv sync
uv run uvicorn app.main:app --app-dir src --reload
```

Neither Monitoring nor Log Analysis needs an LLM key — only Root Cause onward does. To see the deterministic output directly (without needing a key at all), invoke the two agents directly:

```bash
uv run python -c "
from app.agents.nodes.monitoring_agent import monitoring_agent
from app.agents.nodes.log_analysis_agent import log_analysis_agent
from app.agents.state.investigation_state import InvestigationState
import json

logs = open('some.log').read()
state = InvestigationState(logs=logs)
state = state.model_copy(update=monitoring_agent(state))
state = state.model_copy(update=log_analysis_agent(state))
print(json.dumps(state.model_dump(exclude={'logs'}), indent=2))
"
```

## How to test it

```bash
cd backend
uv run pytest -v
uv run ruff check .
```

## Verification performed

- `uv run pytest -v` — 29/29 passing, including:
  - `tests/unit/test_log_analyzer.py` (9 new tests) — stack trace extraction, repeated-failure grouping, both anomaly rules, component extraction, and the case-sensitivity regression test.
  - `tests/unit/test_investigation_graph.py` — updated: the full-pipeline test now expects 3 LLM calls (Root Cause, Recommendation, Report), not 4; the short-circuit test still expects 0.
- `uv run ruff check .` — clean.
- **Live verification against realistic, multi-incident logs** (payments-db timeouts repeating 3x, a Python traceback, an isolated CRITICAL event), invoking the agents directly: correctly extracted the `ZeroDivisionError` stack trace with its full frame text, correctly grouped the 3 timeout errors into one `RepeatedFailure` with `count: 3` despite differing durations in each message, correctly flagged both the isolated critical event and the error burst, and correctly identified `["payments-db", "checkout-service"]` as affected components.
- **Live smoke test via the real upload endpoint**: logs with real errors correctly ran both deterministic agents and then failed with a clear `503` only once Root Cause needed the (unconfigured) LLM — confirming the redesign didn't disturb the lazy-provider behavior from Feature 6.

## Decisions worth calling out

- **Log Analysis re-parses the logs independently of Monitoring** rather than reusing its (capped) sample lists — see ARCHITECTURE.md for the reasoning.
- **Signature normalization for repeated-failure grouping** (strip timestamp, collapse digits) is a deliberate, documented heuristic — it groups the *shape* of a recurring failure, not just byte-identical lines, which is what makes it useful for real logs where every occurrence has a different duration/id/timestamp.
- **Two anomaly rules, not a general statistical engine** — isolated-critical and burst detection are concrete, testable, and directly useful; a fuller anomaly-detection system (baselines, seasonality, etc.) would be speculative complexity this project's rules avoid until there's a demonstrated need.

## What's next

Per the original roadmap: Root Cause/Recommendation/Report remain LLM-backed and still need a real API key to exercise end-to-end (not yet verified in this environment). Log upload & storage, Agent Skills, MCP, guardrails, and evaluation remain pending.

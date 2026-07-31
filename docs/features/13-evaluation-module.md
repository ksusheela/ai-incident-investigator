# Feature 13: Evaluation Module + Dashboard Display

Builds out `app/evaluation/` (scaffolded since the folder-structure pass, empty until now) into a working evaluation module measuring four things for every confirmed incident — response time, confidence, root-cause quality, recommendation quality — and displays the aggregate on the frontend Dashboard.

## What was built

- **`app/evaluation/models.py`** — `QualityCheck` (one named pass/fail criterion + explanation), `QualityScore` (fraction of checks passed + the checks themselves), `EvaluationResult` (one incident's full evaluation), `EvaluationSummary` (averages across every evaluated incident, for the dashboard).
- **`app/evaluation/metrics.py`** — `evaluate_root_cause_quality()` (4 rule-based checks: detailed reasoning, evidence-referencing reasoning, contributing factors present, matched a known pattern) and `evaluate_recommendation_quality()` (3 checks: at least one recommendation, detailed rationales, spans multiple categories).
- **`app/evaluation/evaluator.py`** — `evaluate_investigation()` (combines response time + `root_cause.confidence_score` + both quality scores into one `EvaluationResult`) and `summarize_evaluations()` (averages a list of them into an `EvaluationSummary`).
- **`app/infrastructure/filesystem/artifact_store.py`** — extended with `save_evaluation`/`read_evaluation`/`list_evaluations`, persisting a fourth file (`evaluation.json`) per confirmed incident.
- **`app/services/investigation_service.py`** — measures wall-clock response time around the graph invocation, and (only for confirmed incidents) evaluates and persists the result right after `save_incident()`.
- **`app/api/evaluations.py`** — new `GET /api/v1/evaluations/summary`, no LLM dependency, reads persisted evaluations and returns the aggregate.
- **Frontend**: `types/evaluation.ts`, `services/evaluationService.ts`, and a new `EvaluationSummaryCard` on `DashboardPage.tsx` (three-column responsive grid now, alongside the existing System Status and Recent Incidents cards).

See `ARCHITECTURE.md` → "Evaluation module" for the full design and reasoning.

## Why rule-based quality rubrics, not an LLM judge

Same reasoning already established for Monitoring and Log Analysis: these checks measure presence and specificity (is there a hypothesis, does it cite evidence, is there more than one recommendation category) — mechanically verifiable facts about the output's *shape*. They can't tell you whether a hypothesis is actually *correct*; that would need human review or a real LLM-as-judge call (what DeepEval's metrics do), which is heavier, costs another LLM call, and isn't verifiable in this environment anyway with no API key configured. A rubric that scores the same input identically every time is also the only kind of evaluation this feature can prove actually works without a live model — and every `QualityCheck` carries its own explanation, so the score is never just an opaque number.

## How to run it

```bash
cd backend
uv sync
uv run uvicorn app.main:app --app-dir src --reload
```

```bash
curl http://localhost:8000/api/v1/evaluations/summary
# -> {"evaluated_count": 0, "avg_response_time_seconds": null, ...} with nothing evaluated yet
```

Run a real (fake-LLM-backed, since no API key is configured in this environment) investigation to populate one, directly in Python:

```bash
uv run python -c "
import asyncio, json
from app.agents.skills.loader import SkillLoader
from app.infrastructure.filesystem.artifact_store import get_artifact_store
from app.services.investigation_service import run_investigation

class FakeLLM:
    def __init__(self, responses): self._responses = list(responses)
    async def complete(self, *, system, prompt): return self._responses.pop(0)

responses = [
    json.dumps({'hypothesis': 'x', 'matched_pattern': 'connection_pool_exhaustion', 'confidence_score': 0.85, 'reasoning': 'Repeated timeout errors correlated with an error burst indicate exhaustion.', 'contributing_factors': ['a']}),
    json.dumps({'code_fixes': [], 'configuration_changes': [{'description': 'd', 'rationale': 'The pool is undersized for current peak traffic levels observed.'}], 'database_improvements': []}),
    json.dumps({'summary': 's', 'next_steps': ['n']}),
]

async def main():
    state = await run_investigation(
        logs='ERROR checkout-service: 500\\nERROR checkout-service: db timeout',
        llm=FakeLLM(responses), skill_loader=SkillLoader(), artifact_store=get_artifact_store(),
    )
    print(state.incident_id)

asyncio.run(main())
"
curl http://localhost:8000/api/v1/evaluations/summary
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```
Visit the Dashboard — the "Evaluation" card shows the same aggregate.

## How to test it

```bash
cd backend && uv run pytest -v && uv run ruff check .
cd frontend && npm run test && npm run lint && npx tsc -b
```

## Verification performed

- Backend: `uv run pytest -v` — 126/126 passing, including:
  - `tests/unit/test_evaluation_metrics.py` (9 tests) — each quality check individually, both passing and failing.
  - `tests/unit/test_evaluator.py` (4 tests) — `evaluate_investigation()`'s field mapping and its precondition assertion; `summarize_evaluations()`'s averaging, including the empty case (`None`, not `0`).
  - `tests/unit/test_artifact_store.py` (+5 new tests) — `save_evaluation`/`read_evaluation`/`list_evaluations`, including skipping incidents with no evaluation and raising for an unknown incident.
  - `tests/integration/test_evaluations_api.py` (3 tests) — empty summary with no incidents, correct aggregate after one confirmed incident, and confirmation that a clean (no-incident) investigation doesn't affect the summary.
  - `uv run ruff check .` — clean.
- Frontend: `npm run test` — 8/8 passing, including 3 new `DashboardPage` tests (populated, empty, error states) with the evaluation service mocked via `vi.mock`. `npm run lint`, `npx tsc -b`, and `npm run build` all clean.
- **Live, end-to-end, with real numbers**: started the server, confirmed an empty summary (`evaluated_count: 0`, all averages `null`); ran a real investigation via a direct Python call with a fake LLM (no API key needed for the pipeline mechanics, matching the honest testing approach used throughout this project); confirmed the summary endpoint then returned `evaluated_count: 1`, `avg_response_time_seconds: 0.0223` (real measured wall-clock time), `avg_confidence_score: 0.85` (exact match to the fake root cause's `confidence_score`), `avg_root_cause_quality: 1.0` (all 4 checks legitimately passed), and `avg_recommendation_quality: 0.667` (2 of 3 checks passed — correctly reflects that only one of three recommendation categories was populated).

## Decisions worth calling out

- **Only confirmed incidents are evaluated** — same gate as artifact persistence; there's nothing to score for clean logs, and scoring "nothing happened" would double-count what Monitoring already reports.
- **Confidence is captured, not recomputed** — it's already a real, validated field from Root Cause (Feature 8); evaluation's job is to surface and aggregate it, not derive a second opinion.
- **Averages are `None` when there's no data, never `0`** — a real design choice in `EvaluationSummary`, since `0` would misleadingly read as a real, poor score.
- **The Dashboard card follows the exact established pattern** (loading/error/empty/success via `useAsync`) rather than inventing a new one — consistency across cards matters more than any card being special.

## What's next

Per the original roadmap: guardrails remain pending. A genuine LLM-as-judge evaluation (real DeepEval integration) could complement this rule-based rubric later, if the project reaches the point of needing to judge actual correctness rather than output shape — that would need a real API key to exercise, which this environment doesn't have.

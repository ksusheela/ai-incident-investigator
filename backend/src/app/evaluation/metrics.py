"""Deterministic quality rubrics for Root Cause and Recommendation outputs.

Rule-based, like Monitoring and Log Analysis, and for the same reason:
these checks measure presence and specificity of content — precisely
measurable facts about the output's shape — not whether the hypothesis is
actually *true*. Genuinely judging correctness would need either human
review or an LLM-as-judge call (real DeepEval metrics work this way);
that's a heavier, costlier evaluation this project can add later if
needed, and isn't verifiable in this environment anyway with no LLM key
configured. A rubric that always passes/fails the same way given the same
input is also the only kind of evaluation this feature can actually prove
works without a live model.
"""

from app.agents.state.investigation_state import RecommendationResult, RootCauseResult
from app.evaluation.models import QualityCheck, QualityScore

_MIN_REASONING_WORDS = 15
_MIN_RATIONALE_WORDS = 6
_EVIDENCE_KEYWORDS = (
    "error",
    "exception",
    "timeout",
    "trace",
    "repeated",
    "anomaly",
    "failure",
    "critical",
    "burst",
)


def _word_count(text: str) -> int:
    return len(text.split())


def _score_from_checks(checks: list[QualityCheck]) -> QualityScore:
    score = sum(1 for check in checks if check.passed) / len(checks)
    return QualityScore(score=score, checks=checks)


def evaluate_root_cause_quality(root_cause: RootCauseResult) -> QualityScore:
    """Score a `RootCauseResult` against four presence/specificity checks."""
    reasoning_words = _word_count(root_cause.reasoning)
    reasoning_lower = root_cause.reasoning.lower()

    checks = [
        QualityCheck(
            name="reasoning_detailed",
            passed=reasoning_words >= _MIN_REASONING_WORDS,
            detail=f"reasoning is {reasoning_words} word(s) (>= {_MIN_REASONING_WORDS} required)",
        ),
        QualityCheck(
            name="reasoning_references_evidence",
            passed=any(keyword in reasoning_lower for keyword in _EVIDENCE_KEYWORDS),
            detail="reasoning mentions concrete evidence-related terms",
        ),
        QualityCheck(
            name="contributing_factors_present",
            passed=len(root_cause.contributing_factors) > 0,
            detail=f"{len(root_cause.contributing_factors)} contributing factor(s) listed",
        ),
        QualityCheck(
            name="matched_known_pattern",
            passed=root_cause.matched_pattern is not None,
            detail=f"matched pattern: {root_cause.matched_pattern}"
            if root_cause.matched_pattern
            else "no known pattern matched",
        ),
    ]
    return _score_from_checks(checks)


def evaluate_recommendation_quality(recommendations: RecommendationResult) -> QualityScore:
    """Score a `RecommendationResult` against three presence/diversity checks."""
    categories = (
        recommendations.code_fixes,
        recommendations.configuration_changes,
        recommendations.database_improvements,
    )
    all_recommendations = [rec for category in categories for rec in category]
    categories_used = sum(1 for category in categories if category)

    checks = [
        QualityCheck(
            name="at_least_one_recommendation",
            passed=len(all_recommendations) > 0,
            detail=f"{len(all_recommendations)} recommendation(s) produced",
        ),
        QualityCheck(
            name="rationales_detailed",
            passed=bool(all_recommendations)
            and all(
                _word_count(rec.rationale) >= _MIN_RATIONALE_WORDS for rec in all_recommendations
            ),
            detail=f"all rationales >= {_MIN_RATIONALE_WORDS} words"
            if all_recommendations
            else "no recommendations to check",
        ),
        QualityCheck(
            name="spans_multiple_categories",
            passed=categories_used > 1,
            detail=f"{categories_used} of 3 categories used",
        ),
    ]
    return _score_from_checks(checks)


__all__ = ["evaluate_recommendation_quality", "evaluate_root_cause_quality"]

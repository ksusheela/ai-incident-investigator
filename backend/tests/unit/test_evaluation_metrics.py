"""Unit tests for the deterministic quality-rubric metrics."""

from app.agents.state.investigation_state import (
    Recommendation,
    RecommendationResult,
    RootCauseResult,
)
from app.evaluation.metrics import evaluate_recommendation_quality, evaluate_root_cause_quality

_DETAILED_REASONING = (
    "Repeated connection timeout errors to payments-db, correlated with an "
    "error burst, strongly indicate the connection pool is exhausted under load."
)


def _root_cause(
    *,
    reasoning: str = _DETAILED_REASONING,
    contributing_factors: list[str] | None = None,
    matched_pattern: str | None = "connection_pool_exhaustion",
) -> RootCauseResult:
    return RootCauseResult(
        hypothesis="payments-db connection pool exhaustion",
        matched_pattern=matched_pattern,
        confidence_score=0.85,
        reasoning=reasoning,
        contributing_factors=contributing_factors if contributing_factors is not None else ["x"],
    )


def test_root_cause_quality_scores_1_when_all_checks_pass():
    score = evaluate_root_cause_quality(_root_cause())

    assert score.score == 1.0
    assert all(check.passed for check in score.checks)


def test_root_cause_quality_penalizes_short_reasoning():
    score = evaluate_root_cause_quality(_root_cause(reasoning="Pool exhausted."))

    reasoning_check = next(c for c in score.checks if c.name == "reasoning_detailed")
    assert reasoning_check.passed is False
    assert score.score < 1.0


def test_root_cause_quality_penalizes_reasoning_with_no_evidence_terms():
    score = evaluate_root_cause_quality(
        _root_cause(reasoning="The system probably had some kind of issue happening somewhere.")
    )

    evidence_check = next(c for c in score.checks if c.name == "reasoning_references_evidence")
    assert evidence_check.passed is False


def test_root_cause_quality_penalizes_missing_contributing_factors():
    score = evaluate_root_cause_quality(_root_cause(contributing_factors=[]))

    factors_check = next(c for c in score.checks if c.name == "contributing_factors_present")
    assert factors_check.passed is False


def test_root_cause_quality_penalizes_no_matched_pattern():
    score = evaluate_root_cause_quality(_root_cause(matched_pattern=None))

    pattern_check = next(c for c in score.checks if c.name == "matched_known_pattern")
    assert pattern_check.passed is False


def _recommendation_result(
    *,
    code_fixes: list[Recommendation] | None = None,
    configuration_changes: list[Recommendation] | None = None,
    database_improvements: list[Recommendation] | None = None,
) -> RecommendationResult:
    detailed = Recommendation(
        description="Increase connection pool size",
        rationale="The pool is undersized for current peak traffic levels observed.",
    )
    resolved_config = configuration_changes if configuration_changes is not None else [detailed]
    resolved_db = database_improvements if database_improvements is not None else [detailed]
    return RecommendationResult(
        code_fixes=code_fixes if code_fixes is not None else [],
        configuration_changes=resolved_config,
        database_improvements=resolved_db,
    )


def test_recommendation_quality_scores_1_when_all_checks_pass():
    score = evaluate_recommendation_quality(_recommendation_result())

    assert score.score == 1.0
    assert all(check.passed for check in score.checks)


def test_recommendation_quality_fails_at_least_one_check_when_empty():
    empty = RecommendationResult(code_fixes=[], configuration_changes=[], database_improvements=[])

    score = evaluate_recommendation_quality(empty)

    at_least_one = next(c for c in score.checks if c.name == "at_least_one_recommendation")
    assert at_least_one.passed is False
    assert score.score == 0.0


def test_recommendation_quality_penalizes_terse_rationale():
    terse = Recommendation(description="Fix it", rationale="Just fix it.")
    result = _recommendation_result(configuration_changes=[terse], database_improvements=[])

    score = evaluate_recommendation_quality(result)

    detail_check = next(c for c in score.checks if c.name == "rationales_detailed")
    assert detail_check.passed is False


def test_recommendation_quality_penalizes_single_category():
    detailed = Recommendation(
        description="Increase connection pool size",
        rationale="The pool is undersized for current peak traffic levels observed.",
    )
    result = _recommendation_result(configuration_changes=[detailed], database_improvements=[])

    score = evaluate_recommendation_quality(result)

    diversity_check = next(c for c in score.checks if c.name == "spans_multiple_categories")
    assert diversity_check.passed is False

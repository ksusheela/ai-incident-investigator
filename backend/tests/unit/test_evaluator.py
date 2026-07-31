"""Unit tests for evaluate_investigation() and summarize_evaluations()."""

import pytest

from app.agents.state.investigation_state import (
    InvestigationState,
    MonitoringResult,
    Recommendation,
    RecommendationResult,
    RootCauseResult,
)
from app.evaluation.evaluator import evaluate_investigation, summarize_evaluations
from app.evaluation.models import EvaluationResult, QualityCheck, QualityScore


def _evaluated_state(
    *, incident_id: str = "abc123", confidence_score: float = 0.8
) -> InvestigationState:
    return InvestigationState(
        logs="ERROR something broke",
        incident_id=incident_id,
        monitoring=MonitoringResult(
            incident_detected=True,
            severity="medium",
            summary="Detected 1 error line(s); severity: medium.",
            error_count=1,
            warning_count=0,
            sample_errors=[],
            sample_warnings=[],
        ),
        root_cause=RootCauseResult(
            hypothesis="x",
            matched_pattern="connection_pool_exhaustion",
            confidence_score=confidence_score,
            reasoning="Repeated timeout errors correlated with an error burst indicate exhaustion.",
            contributing_factors=["undersized pool"],
        ),
        recommendations=RecommendationResult(
            code_fixes=[],
            configuration_changes=[
                Recommendation(
                    description="Increase pool size",
                    rationale="The pool is undersized for current peak traffic levels.",
                )
            ],
            database_improvements=[],
        ),
    )


def test_evaluate_investigation_captures_response_time_and_confidence():
    result = evaluate_investigation(state=_evaluated_state(), response_time_seconds=1.23)

    assert result.incident_id == "abc123"
    assert result.response_time_seconds == 1.23
    assert result.confidence_score == 0.8
    assert 0.0 <= result.root_cause_quality.score <= 1.0
    assert 0.0 <= result.recommendation_quality.score <= 1.0


def test_evaluate_investigation_requires_incident_id():
    state = _evaluated_state().model_copy(update={"incident_id": None})

    with pytest.raises(AssertionError):
        evaluate_investigation(state=state, response_time_seconds=1.0)


def _evaluation(
    *,
    response_time_seconds: float,
    confidence_score: float,
    root_cause_score: float,
    recommendation_score: float,
) -> EvaluationResult:
    passing_check = QualityCheck(name="x", passed=True, detail="d")
    return EvaluationResult(
        incident_id="x",
        evaluated_at="2026-07-31T00:00:00+00:00",
        response_time_seconds=response_time_seconds,
        confidence_score=confidence_score,
        root_cause_quality=QualityScore(score=root_cause_score, checks=[passing_check]),
        recommendation_quality=QualityScore(score=recommendation_score, checks=[passing_check]),
    )


def test_summarize_evaluations_computes_averages():
    evaluations = [
        _evaluation(
            response_time_seconds=1.0,
            confidence_score=0.6,
            root_cause_score=0.5,
            recommendation_score=1.0,
        ),
        _evaluation(
            response_time_seconds=3.0,
            confidence_score=1.0,
            root_cause_score=1.0,
            recommendation_score=0.0,
        ),
    ]

    summary = summarize_evaluations(evaluations)

    assert summary.evaluated_count == 2
    assert summary.avg_response_time_seconds == 2.0
    assert summary.avg_confidence_score == 0.8
    assert summary.avg_root_cause_quality == 0.75
    assert summary.avg_recommendation_quality == 0.5


def test_summarize_evaluations_returns_none_averages_when_empty():
    summary = summarize_evaluations([])

    assert summary.evaluated_count == 0
    assert summary.avg_response_time_seconds is None
    assert summary.avg_confidence_score is None
    assert summary.avg_root_cause_quality is None
    assert summary.avg_recommendation_quality is None

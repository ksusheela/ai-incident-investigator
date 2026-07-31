"""Combines response time, confidence, and the quality rubrics into one
EvaluationResult, and aggregates many of them into a dashboard summary."""

from datetime import UTC, datetime

from app.agents.state.investigation_state import InvestigationState
from app.evaluation.metrics import evaluate_recommendation_quality, evaluate_root_cause_quality
from app.evaluation.models import EvaluationResult, EvaluationSummary


def evaluate_investigation(
    *, state: InvestigationState, response_time_seconds: float
) -> EvaluationResult:
    """Evaluate a confirmed incident's investigation.

    Requires `state.incident_id`, `state.root_cause`, and
    `state.recommendations` to already be populated — call this only after
    `IncidentArtifactStore.save_incident()` has assigned the incident_id.
    """
    assert state.incident_id is not None, "evaluate_investigation requires a persisted incident"
    assert state.root_cause is not None, "evaluate_investigation requires root_cause"
    assert state.recommendations is not None, "evaluate_investigation requires recommendations"

    return EvaluationResult(
        incident_id=state.incident_id,
        evaluated_at=datetime.now(UTC).isoformat(),
        response_time_seconds=response_time_seconds,
        confidence_score=state.root_cause.confidence_score,
        root_cause_quality=evaluate_root_cause_quality(state.root_cause),
        recommendation_quality=evaluate_recommendation_quality(state.recommendations),
    )


def summarize_evaluations(evaluations: list[EvaluationResult]) -> EvaluationSummary:
    """Aggregate a list of evaluations into dashboard-ready averages."""
    if not evaluations:
        return EvaluationSummary(
            evaluated_count=0,
            avg_response_time_seconds=None,
            avg_confidence_score=None,
            avg_root_cause_quality=None,
            avg_recommendation_quality=None,
        )

    count = len(evaluations)
    return EvaluationSummary(
        evaluated_count=count,
        avg_response_time_seconds=sum(e.response_time_seconds for e in evaluations) / count,
        avg_confidence_score=sum(e.confidence_score for e in evaluations) / count,
        avg_root_cause_quality=sum(e.root_cause_quality.score for e in evaluations) / count,
        avg_recommendation_quality=sum(e.recommendation_quality.score for e in evaluations) / count,
    )


__all__ = ["evaluate_investigation", "summarize_evaluations"]

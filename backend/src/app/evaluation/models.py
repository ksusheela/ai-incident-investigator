"""Data models for the evaluation module."""

from pydantic import BaseModel, Field


class QualityCheck(BaseModel):
    """One pass/fail criterion in a quality rubric, with a human-readable reason."""

    name: str
    passed: bool
    detail: str


class QualityScore(BaseModel):
    """A rubric-based quality score: the fraction of `checks` that passed."""

    score: float = Field(ge=0.0, le=1.0)
    checks: list[QualityCheck]


class EvaluationResult(BaseModel):
    """Evaluation of one confirmed incident's investigation."""

    incident_id: str
    evaluated_at: str
    response_time_seconds: float = Field(ge=0.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    root_cause_quality: QualityScore
    recommendation_quality: QualityScore


class EvaluationSummary(BaseModel):
    """Aggregate evaluation metrics across every evaluated incident, for the dashboard.

    Averages are `None` (not zero) when `evaluated_count` is 0 — there is
    no meaningful average of nothing, and zero would misleadingly look
    like a real, poor score.
    """

    evaluated_count: int
    avg_response_time_seconds: float | None
    avg_confidence_score: float | None
    avg_root_cause_quality: float | None
    avg_recommendation_quality: float | None

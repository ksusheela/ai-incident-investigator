"""Shared LangGraph state for the incident-investigation pipeline.

Each agent node reads the fields it needs and returns a partial update for
the fields it owns; no two agents write the same field.
"""

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["none", "low", "medium", "high", "critical"]


class MonitoringResult(BaseModel):
    """Structured triage output produced by the (deterministic) Monitoring Agent."""

    incident_detected: bool
    severity: Severity
    summary: str
    error_count: int
    warning_count: int
    sample_errors: list[str]
    sample_warnings: list[str]


class StackTrace(BaseModel):
    """A single stack trace extracted from the raw logs."""

    exception_type: str
    message: str
    raw_text: str


class RepeatedFailure(BaseModel):
    """A group of error lines judged to be the same underlying failure."""

    signature: str
    example_message: str
    count: int
    first_seen: str | None
    last_seen: str | None


class LogAnalysisResult(BaseModel):
    """Structured findings produced by the (deterministic) Log Analysis Agent."""

    affected_components: list[str]
    time_range: str
    stack_traces: list[StackTrace]
    repeated_failures: list[RepeatedFailure]
    anomalies: list[str]


class RootCauseResult(BaseModel):
    """The Root Cause Agent's hypothesis about why the incident occurred."""

    hypothesis: str
    matched_pattern: str | None
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    contributing_factors: list[str]


class Recommendation(BaseModel):
    """A single suggested fix, with the reasoning behind it."""

    description: str
    rationale: str


class RecommendationResult(BaseModel):
    """The Recommendation Agent's suggested fixes, grouped by category.

    A category is an empty list, not omitted, when it doesn't apply to
    this particular root cause — e.g. most incidents won't need a
    database improvement.
    """

    code_fixes: list[Recommendation]
    configuration_changes: list[Recommendation]
    database_improvements: list[Recommendation]


class ReportSections(BaseModel):
    """The Report Agent's LLM-authored narrative pieces.

    Everything else in the final report (Root Cause, Evidence, Confidence,
    Recommendation) is rendered deterministically from already-validated
    state — see `app/agents/nodes/report_renderer.py` — since those facts
    already exist and shouldn't risk being restated inconsistently by an
    LLM. Only the parts that genuinely need synthesis/writing are
    LLM-authored.
    """

    summary: str
    next_steps: list[str]


class InvestigationState(BaseModel):
    """The graph's state, threaded through every node in the pipeline."""

    logs: str

    # Written by the Monitoring Agent.
    monitoring: MonitoringResult | None = None

    # Written by the Log Analysis Agent.
    log_analysis: LogAnalysisResult | None = None

    # Written by the Root Cause Agent.
    root_cause: RootCauseResult | None = None

    # Written by the Recommendation Agent.
    recommendations: RecommendationResult | None = None

    # Written by the Report Agent — the final human-readable deliverable.
    report: str | None = None

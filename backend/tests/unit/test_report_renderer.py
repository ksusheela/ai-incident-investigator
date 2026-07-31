"""Unit tests for the deterministic Markdown report template.

No LLM involved — these exercise render_incident_report_markdown() and
categorize_confidence_label() directly against constructed state.
"""

from app.agents.nodes.report_renderer import (
    categorize_confidence_label,
    render_incident_report_markdown,
)
from app.agents.state.investigation_state import (
    InvestigationState,
    LogAnalysisResult,
    MonitoringResult,
    Recommendation,
    RecommendationResult,
    RepeatedFailure,
    ReportSections,
    RootCauseResult,
    StackTrace,
)


def _full_state(*, confidence_score: float = 0.85) -> InvestigationState:
    return InvestigationState(
        logs="irrelevant",
        monitoring=MonitoringResult(
            incident_detected=True,
            severity="medium",
            summary="Detected 2 error line(s); severity: medium.",
            error_count=2,
            warning_count=0,
            sample_errors=[],
            sample_warnings=[],
        ),
        log_analysis=LogAnalysisResult(
            affected_components=["payments-db"],
            time_range="2026-07-31T14:02:00 to 2026-07-31T14:02:10",
            stack_traces=[
                StackTrace(
                    exception_type="ZeroDivisionError",
                    message="division by zero",
                    raw_text="Traceback...\nZeroDivisionError: division by zero",
                )
            ],
            repeated_failures=[
                RepeatedFailure(
                    signature="ERROR payments-db: connection timed out after #ms",
                    example_message="connection timed out after 3013ms",
                    count=3,
                    first_seen="2026-07-31T14:02:00",
                    last_seen="2026-07-31T14:02:10",
                )
            ],
            anomalies=["Error burst: 5 errors within 60s"],
        ),
        root_cause=RootCauseResult(
            hypothesis="payments-db connection pool exhaustion",
            matched_pattern="connection_pool_exhaustion",
            confidence_score=confidence_score,
            reasoning="Repeated timeouts under load match this pattern.",
            contributing_factors=["undersized connection pool"],
        ),
        recommendations=RecommendationResult(
            code_fixes=[],
            configuration_changes=[
                Recommendation(
                    description="Increase connection pool size",
                    rationale="Pool is undersized for current load.",
                )
            ],
            database_improvements=[],
        ),
    )


def test_render_includes_all_six_required_sections_in_order():
    report = render_incident_report_markdown(
        _full_state(),
        ReportSections(summary="Checkout failed due to DB timeouts.", next_steps=["Notify team"]),
    )

    headings = [
        "## Summary",
        "## Root Cause",
        "## Evidence",
        "## Confidence",
        "## Recommendation",
        "## Next Steps",
    ]
    positions = [report.index(h) for h in headings]

    assert positions == sorted(positions), "sections must appear in the required order"


def test_render_includes_llm_authored_summary_and_next_steps():
    report = render_incident_report_markdown(
        _full_state(),
        ReportSections(summary="Checkout failed due to DB timeouts.", next_steps=["Notify team"]),
    )

    assert "Checkout failed due to DB timeouts." in report
    assert "- Notify team" in report


def test_render_root_cause_section_reflects_structured_data_not_llm_text():
    report = render_incident_report_markdown(
        _full_state(),
        ReportSections(summary="x", next_steps=["y"]),
    )

    assert "payments-db connection pool exhaustion" in report
    assert "connection_pool_exhaustion" in report
    assert "Repeated timeouts under load match this pattern." in report


def test_render_evidence_section_includes_stack_traces_repeated_failures_and_anomalies():
    report = render_incident_report_markdown(
        _full_state(),
        ReportSections(summary="x", next_steps=["y"]),
    )

    assert "ZeroDivisionError" in report
    assert "x3" in report
    assert "Error burst" in report


def test_render_confidence_section_shows_percentage_and_label():
    report = render_incident_report_markdown(
        _full_state(confidence_score=0.85),
        ReportSections(summary="x", next_steps=["y"]),
    )

    assert "85% (High)" in report


def test_render_recommendation_section_omits_empty_categories():
    report = render_incident_report_markdown(
        _full_state(),
        ReportSections(summary="x", next_steps=["y"]),
    )

    assert "Code fixes:" not in report
    assert "Configuration changes:" in report
    assert "Database improvements:" not in report


def test_categorize_confidence_label_thresholds():
    assert categorize_confidence_label(0.9) == "High"
    assert categorize_confidence_label(0.8) == "High"
    assert categorize_confidence_label(0.79) == "Medium"
    assert categorize_confidence_label(0.5) == "Medium"
    assert categorize_confidence_label(0.49) == "Low"
    assert categorize_confidence_label(0.0) == "Low"

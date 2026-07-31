"""Deterministic Markdown template for the final incident report.

Root Cause, Evidence, Confidence, and Recommendation are rendered directly
from already-validated structured state — no LLM involved, so the report
can never contradict data the pipeline already produced (e.g. stating a
different confidence score in prose than `confidence_score` itself holds).
Only Summary and Next Steps come from the Report Agent's LLM call (see
`report_agent.py`), since those genuinely require synthesis/writing
rather than restating existing data.
"""

from app.agents.state.investigation_state import (
    InvestigationState,
    Recommendation,
    ReportSections,
)

_CONFIDENCE_HIGH_THRESHOLD = 0.8
_CONFIDENCE_MEDIUM_THRESHOLD = 0.5


def categorize_confidence_label(score: float) -> str:
    """Map a 0.0-1.0 confidence score to a human-readable label."""
    if score >= _CONFIDENCE_HIGH_THRESHOLD:
        return "High"
    if score >= _CONFIDENCE_MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


def _render_evidence_section(state: InvestigationState) -> str:
    assert state.monitoring is not None
    assert state.log_analysis is not None

    lines = [f"- **Monitoring summary:** {state.monitoring.summary}"]

    if state.log_analysis.stack_traces:
        lines.append("- **Stack traces:**")
        lines += [
            f"  - `{trace.exception_type}`: {trace.message}"
            for trace in state.log_analysis.stack_traces
        ]

    if state.log_analysis.repeated_failures:
        lines.append("- **Repeated failures:**")
        lines += [
            f"  - {failure.example_message} (x{failure.count}, "
            f"{failure.first_seen} to {failure.last_seen})"
            for failure in state.log_analysis.repeated_failures
        ]

    if state.log_analysis.anomalies:
        lines.append("- **Anomalies:**")
        lines += [f"  - {anomaly}" for anomaly in state.log_analysis.anomalies]

    return "\n".join(lines)


def _render_recommendation_category(title: str, items: list[Recommendation]) -> str | None:
    if not items:
        return None
    bullets = "\n".join(f"- {item.description} — {item.rationale}" for item in items)
    return f"**{title}:**\n{bullets}"


def _render_recommendation_section(state: InvestigationState) -> str:
    assert state.recommendations is not None
    recs = state.recommendations

    categories = [
        _render_recommendation_category("Code fixes", recs.code_fixes),
        _render_recommendation_category("Configuration changes", recs.configuration_changes),
        _render_recommendation_category("Database improvements", recs.database_improvements),
    ]
    return "\n\n".join(category for category in categories if category is not None)


def render_incident_report_markdown(state: InvestigationState, sections: ReportSections) -> str:
    """Assemble the final report: Summary, Root Cause, Evidence, Confidence,
    Recommendation, Next Steps — in that order, every section always present."""
    assert state.monitoring is not None, "report rendering requires monitoring"
    assert state.log_analysis is not None, "report rendering requires log_analysis"
    assert state.root_cause is not None, "report rendering requires root_cause"
    assert state.recommendations is not None, "report rendering requires recommendations"

    root_cause = state.root_cause
    confidence_label = categorize_confidence_label(root_cause.confidence_score)
    matched_pattern = root_cause.matched_pattern or "no known pattern matched"
    next_steps = "\n".join(f"- {step}" for step in sections.next_steps)

    return f"""# Incident Report

## Summary

{sections.summary}

## Root Cause

**Hypothesis:** {root_cause.hypothesis}

**Matched pattern:** {matched_pattern}

{root_cause.reasoning}

## Evidence

{_render_evidence_section(state)}

## Confidence

**{root_cause.confidence_score:.0%} ({confidence_label})**

## Recommendation

{_render_recommendation_section(state)}

## Next Steps

{next_steps}
"""


__all__ = ["categorize_confidence_label", "render_incident_report_markdown"]

"""Monitoring Agent — deterministic first-pass log triage.

Responsibilities: detect errors, detect warnings, categorize severity, and
produce an incident summary. See `log_parser.py` for why this is
rule-based rather than LLM-based.
"""

from app.agents.nodes.log_parser import (
    build_incident_summary,
    categorize_severity,
    classify_log_lines,
)
from app.agents.state.investigation_state import InvestigationState, MonitoringResult

_MAX_SAMPLE_LINES = 20


def monitoring_agent(state: InvestigationState) -> dict:
    classification = classify_log_lines(state.logs)
    error_count = len(classification.error_lines)
    warning_count = len(classification.warning_lines)
    severity = categorize_severity(error_count=error_count, warning_count=warning_count)

    summary = build_incident_summary(
        error_count=error_count,
        warning_count=warning_count,
        severity=severity,
        sample_errors=classification.error_lines[:3],
        first_timestamp=classification.first_timestamp,
        last_timestamp=classification.last_timestamp,
    )

    result = MonitoringResult(
        incident_detected=error_count > 0,
        severity=severity,
        summary=summary,
        error_count=error_count,
        warning_count=warning_count,
        sample_errors=classification.error_lines[:_MAX_SAMPLE_LINES],
        sample_warnings=classification.warning_lines[:_MAX_SAMPLE_LINES],
    )
    return {"monitoring": result}

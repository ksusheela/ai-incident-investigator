"""Log Analysis Agent — deterministic deep parsing of the raw logs.

Responsibilities: parse logs, extract stack traces, identify repeated
failures, detect anomalies. Rule-based, like the Monitoring Agent — see
`log_analyzer.py` for why.
"""

from app.agents.nodes.log_analyzer import (
    detect_anomalies,
    extract_affected_components,
    extract_stack_traces,
    identify_repeated_failures,
)
from app.agents.nodes.log_parser import classify_log_lines
from app.agents.state.investigation_state import InvestigationState, LogAnalysisResult


def log_analysis_agent(state: InvestigationState) -> dict:
    # Re-classified independently from state.logs rather than reusing
    # state.monitoring's samples: those are capped at 20 lines each for a
    # bounded API response, but deep analysis (repeated-failure counts,
    # anomaly detection) needs the full, uncapped set. Re-running this
    # cheap, pure parse is a deliberate trade-off over threading unbounded
    # internal data through the public response schema.
    classification = classify_log_lines(state.logs)

    time_range = (
        f"{classification.first_timestamp} to {classification.last_timestamp}"
        if classification.first_timestamp and classification.last_timestamp
        else "unknown"
    )

    result = LogAnalysisResult(
        affected_components=extract_affected_components(state.logs),
        time_range=time_range,
        stack_traces=extract_stack_traces(state.logs),
        repeated_failures=identify_repeated_failures(classification.error_lines),
        anomalies=detect_anomalies(classification.error_lines),
    )
    return {"log_analysis": result}

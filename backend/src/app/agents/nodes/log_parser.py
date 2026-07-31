"""Pure, dependency-free log parsing used by the Monitoring Agent.

Deliberately not LLM-based: classifying a log line by severity level and
counting occurrences is a precise, mechanical task that regex handles
reliably, cheaply, and deterministically. An LLM is slower, costlier, and
demonstrably worse at exact counting — reserved for agents further down the
pipeline that need actual reasoning (Log Analysis, Root Cause,
Recommendation, Report), not for this first-pass triage step.
"""

import re
from dataclasses import dataclass

from app.agents.state.investigation_state import Severity

_ERROR_LEVEL_PATTERN = re.compile(r"\b(CRITICAL|FATAL|ERROR|SEVERE)\b", re.IGNORECASE)
_WARNING_LEVEL_PATTERN = re.compile(r"\b(WARN|WARNING)\b", re.IGNORECASE)
_TRACEBACK_PATTERN = re.compile(r"^\s*Traceback \(most recent call last\):")
_TIMESTAMP_PATTERN = re.compile(r"^\s*(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})")

# Error-count thresholds for categorize_severity(). Kept as named constants
# rather than inline numbers so the policy is documented and adjustable
# in one place. Any error at all is at least "medium"; these mark the
# medium->high and high->critical boundaries.
_HIGH_ERROR_THRESHOLD = 5
_CRITICAL_ERROR_THRESHOLD = 20


@dataclass
class LogClassification:
    """Per-line classification of a raw log excerpt."""

    error_lines: list[str]
    warning_lines: list[str]
    total_lines: int
    first_timestamp: str | None
    last_timestamp: str | None


def extract_leading_timestamp(line: str) -> str | None:
    """Return the leading ISO-8601-ish timestamp on `line`, if any.

    Shared with `log_analyzer.py` so both modules agree on what counts as
    a timestamp instead of maintaining two copies of the same regex.
    """
    match = _TIMESTAMP_PATTERN.match(line)
    return match.group(1) if match else None


def classify_log_lines(logs: str) -> LogClassification:
    """Split `logs` into lines and bucket each into errors/warnings by level marker.

    A line matching an error-level marker (CRITICAL/FATAL/ERROR/SEVERE) or
    starting a Python traceback is an error line; a line matching a
    warning-level marker (WARN/WARNING) is a warning line. Also extracts the
    first and last leading ISO-8601-ish timestamps found, if any, for the
    incident summary's time range.
    """
    lines = [line for line in logs.splitlines() if line.strip()]

    error_lines: list[str] = []
    warning_lines: list[str] = []
    timestamps: list[str] = []

    for line in lines:
        if timestamp := extract_leading_timestamp(line):
            timestamps.append(timestamp)

        if _ERROR_LEVEL_PATTERN.search(line) or _TRACEBACK_PATTERN.match(line):
            error_lines.append(line.strip())
        elif _WARNING_LEVEL_PATTERN.search(line):
            warning_lines.append(line.strip())

    return LogClassification(
        error_lines=error_lines,
        warning_lines=warning_lines,
        total_lines=len(lines),
        first_timestamp=timestamps[0] if timestamps else None,
        last_timestamp=timestamps[-1] if timestamps else None,
    )


def categorize_severity(*, error_count: int, warning_count: int) -> Severity:
    """Map error/warning counts to a severity tier.

    Any errors at all mean an incident; the tier scales with volume. Warnings
    alone are noted but don't constitute an incident on their own.
    """
    if error_count == 0:
        return "low" if warning_count > 0 else "none"
    if error_count < _HIGH_ERROR_THRESHOLD:
        return "medium"
    if error_count < _CRITICAL_ERROR_THRESHOLD:
        return "high"
    return "critical"


def build_incident_summary(
    *,
    error_count: int,
    warning_count: int,
    severity: Severity,
    sample_errors: list[str],
    first_timestamp: str | None,
    last_timestamp: str | None,
) -> str:
    """Render a short, human-readable summary of the triage result."""
    parts = [
        f"Detected {error_count} error line(s) and {warning_count} warning line(s); "
        f"severity: {severity}."
    ]

    if first_timestamp and last_timestamp:
        parts.append(f"Time range: {first_timestamp} to {last_timestamp}.")

    if sample_errors:
        parts.append(f"Example: {sample_errors[0]}")

    return " ".join(parts)


__all__ = [
    "LogClassification",
    "build_incident_summary",
    "categorize_severity",
    "classify_log_lines",
    "extract_leading_timestamp",
]

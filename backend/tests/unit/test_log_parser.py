"""Unit tests for the deterministic log-parsing logic behind the Monitoring Agent."""

from app.agents.nodes.log_parser import (
    build_incident_summary,
    categorize_severity,
    classify_log_lines,
)

CLEAN_LOGS = "\n".join(
    [
        "2026-07-31T10:00:00Z INFO checkout-service: request handled in 12ms",
        "2026-07-31T10:00:01Z INFO checkout-service: request handled in 9ms",
    ]
)

NOISY_LOGS = "\n".join(
    [
        "2026-07-31T10:02:11Z WARN checkout-service: connection pool at 80% capacity",
        "2026-07-31T10:02:15Z ERROR checkout-service: 500 Internal Server Error",
        "2026-07-31T10:02:16Z ERROR checkout-service: connection to payments-db timed out",
        "2026-07-31T10:02:20Z CRITICAL checkout-service: payments-db unreachable",
    ]
)


def test_classify_log_lines_finds_no_errors_or_warnings_in_clean_logs():
    result = classify_log_lines(CLEAN_LOGS)

    assert result.error_lines == []
    assert result.warning_lines == []
    assert result.total_lines == 2


def test_classify_log_lines_buckets_errors_and_warnings_separately():
    result = classify_log_lines(NOISY_LOGS)

    # NOISY_LOGS has 2 ERROR lines + 1 CRITICAL line (all error-level) and 1 WARN line.
    assert len(result.error_lines) == 3
    assert len(result.warning_lines) == 1
    assert "500 Internal Server Error" in result.error_lines[0]


def test_classify_log_lines_extracts_timestamp_range():
    result = classify_log_lines(NOISY_LOGS)

    assert result.first_timestamp == "2026-07-31T10:02:11"
    assert result.last_timestamp == "2026-07-31T10:02:20"


def test_classify_log_lines_treats_traceback_as_an_error():
    logs = "Traceback (most recent call last):\n  File \"app.py\", line 1\nValueError: bad input"
    result = classify_log_lines(logs)

    assert len(result.error_lines) == 1


def test_categorize_severity_none_when_nothing_found():
    assert categorize_severity(error_count=0, warning_count=0) == "none"


def test_categorize_severity_low_for_warnings_only():
    assert categorize_severity(error_count=0, warning_count=3) == "low"


def test_categorize_severity_scales_with_error_volume():
    assert categorize_severity(error_count=1, warning_count=0) == "medium"
    assert categorize_severity(error_count=4, warning_count=0) == "medium"
    assert categorize_severity(error_count=5, warning_count=0) == "high"
    assert categorize_severity(error_count=19, warning_count=0) == "high"
    assert categorize_severity(error_count=20, warning_count=0) == "critical"


def test_build_incident_summary_includes_counts_and_severity():
    summary = build_incident_summary(
        error_count=2,
        warning_count=1,
        severity="medium",
        sample_errors=["ERROR: boom"],
        first_timestamp=None,
        last_timestamp=None,
    )

    assert "2 error" in summary
    assert "1 warning" in summary
    assert "medium" in summary
    assert "ERROR: boom" in summary


def test_build_incident_summary_includes_time_range_when_available():
    summary = build_incident_summary(
        error_count=1,
        warning_count=0,
        severity="medium",
        sample_errors=[],
        first_timestamp="2026-07-31T10:00:00",
        last_timestamp="2026-07-31T10:05:00",
    )

    assert "2026-07-31T10:00:00 to 2026-07-31T10:05:00" in summary

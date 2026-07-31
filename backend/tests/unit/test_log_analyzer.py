"""Unit tests for the deterministic deep-analysis logic behind the Log Analysis Agent."""

from app.agents.nodes.log_analyzer import (
    detect_anomalies,
    extract_affected_components,
    extract_stack_traces,
    identify_repeated_failures,
)

TRACEBACK_LOGS = "\n".join(
    [
        "2026-07-31T14:02:00Z ERROR checkout-service: request failed",
        "Traceback (most recent call last):",
        '  File "app.py", line 42, in handle_request',
        "    result = process(payload)",
        '  File "app.py", line 17, in process',
        "    return 1 / count",
        "ZeroDivisionError: division by zero",
        "2026-07-31T14:02:05Z INFO checkout-service: recovered",
    ]
)

REPEATED_FAILURE_LOGS = "\n".join(
    [
        "2026-07-31T14:02:00Z ERROR payments-db: connection timed out after 3013ms",
        "2026-07-31T14:02:05Z ERROR payments-db: connection timed out after 4502ms",
        "2026-07-31T14:02:10Z ERROR payments-db: connection timed out after 2870ms",
        "2026-07-31T14:02:15Z ERROR checkout-service: one-off unrelated failure",
    ]
)


def test_extract_stack_traces_parses_exception_type_and_message():
    traces = extract_stack_traces(TRACEBACK_LOGS)

    assert len(traces) == 1
    assert traces[0].exception_type == "ZeroDivisionError"
    assert traces[0].message == "division by zero"
    assert "handle_request" in traces[0].raw_text


def test_extract_stack_traces_returns_empty_list_when_no_traceback():
    assert extract_stack_traces("INFO: all good") == []


def test_identify_repeated_failures_groups_similar_messages_by_signature():
    error_lines = [line for line in REPEATED_FAILURE_LOGS.splitlines() if "ERROR" in line]

    failures = identify_repeated_failures(error_lines)

    assert len(failures) == 1
    assert failures[0].count == 3
    assert failures[0].first_seen == "2026-07-31T14:02:00"
    assert failures[0].last_seen == "2026-07-31T14:02:10"


def test_identify_repeated_failures_excludes_one_off_errors():
    error_lines = [line for line in REPEATED_FAILURE_LOGS.splitlines() if "ERROR" in line]

    failures = identify_repeated_failures(error_lines)

    assert not any("unrelated failure" in f.example_message for f in failures)


def test_detect_anomalies_flags_isolated_critical_event():
    error_lines = [
        "2026-07-31T14:02:00Z CRITICAL payments-db: primary node unreachable",
    ]

    anomalies = detect_anomalies(error_lines)

    assert any("Isolated critical" in a for a in anomalies)


def test_detect_anomalies_flags_error_burst():
    error_lines = [
        f"2026-07-31T14:02:{i:02d}Z ERROR checkout-service: request {i} failed" for i in range(6)
    ]

    anomalies = detect_anomalies(error_lines)

    assert any("burst" in a.lower() for a in anomalies)


def test_detect_anomalies_empty_for_routine_errors():
    error_lines = ["2026-07-31T14:02:00Z ERROR checkout-service: single routine failure"]

    assert detect_anomalies(error_lines) == []


def test_extract_affected_components_deduplicates_in_order():
    logs = "\n".join(
        [
            "ERROR checkout-service: failure one",
            "WARN payments-db: pool low",
            "ERROR checkout-service: failure two",
        ]
    )

    assert extract_affected_components(logs) == ["checkout-service", "payments-db"]


def test_extract_affected_components_ignores_prose_containing_error_or_warn():
    # Regression test: "500 Internal Server Error" contains the word "Error"
    # (mixed case), which must not be mistaken for a level marker followed
    # by the next line's leading timestamp as a fake "component".
    logs = (
        "2026-07-31T14:02:00Z ERROR checkout-service: 500 Internal Server Error\n"
        "2026-07-31T14:02:05Z ERROR checkout-service: connection to payments-db timed out"
    )

    assert extract_affected_components(logs) == ["checkout-service"]

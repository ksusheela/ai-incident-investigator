"""Pure, dependency-free deep log analysis used by the Log Analysis Agent.

Like `log_parser.py` (the Monitoring Agent's module), this is deliberately
rule-based rather than LLM-based: extracting stack traces, grouping
repeated failures, and flagging statistical anomalies are all mechanical
pattern-matching/counting tasks, not tasks that need judgment. LLM
reasoning is reserved for the agents that actually interpret these
findings — Root Cause, Recommendation, Report.
"""

import re
from collections import Counter, defaultdict
from datetime import datetime

from app.agents.nodes.log_parser import extract_leading_timestamp
from app.agents.state.investigation_state import RepeatedFailure, StackTrace

_TRACEBACK_START = re.compile(r"^\s*Traceback \(most recent call last\):\s*$")
_FRAME_LINE = re.compile(r'^\s*File\s+"[^"]+",\s*line\s+\d+,\s+in\s+\S+')
_EXCEPTION_LINE = re.compile(r"^\s*([\w.]+(?:Error|Exception|Warning))\s*:?\s*(.*)$")

# Intentionally case-sensitive (unlike log_parser's level detection): a
# structured log level marker is conventionally all-uppercase, whereas
# lowercase/mixed-case occurrences of these words are usually just prose
# (e.g. "Internal Server Error"). Matching case-insensitively here caused a
# real false positive — see the regression test for that failure.
_COMPONENT_PATTERN = re.compile(r"\b(?:CRITICAL|FATAL|ERROR|SEVERE|WARN|WARNING)\b\s+([\w.-]+):")
_CRITICAL_LEVEL_PATTERN = re.compile(r"\b(CRITICAL|FATAL)\b", re.IGNORECASE)

_DIGITS_PATTERN = re.compile(r"\d+")
_TIMESTAMP_PREFIX_PATTERN = re.compile(r"^\s*\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}Z?\s*")

_MIN_REPEATED_OCCURRENCES = 2
_BURST_MIN_ERRORS = 5
_BURST_WINDOW_SECONDS = 60


def extract_stack_traces(logs: str) -> list[StackTrace]:
    """Find every Python-style traceback in `logs` and parse it out.

    Recognizes the standard CPython format: a `Traceback (most recent
    call last):` header, one or more `File "...", line N, in <func>` /
    code-line pairs, and a final `ExceptionType: message` line.
    """
    lines = logs.splitlines()
    traces: list[StackTrace] = []
    i = 0

    while i < len(lines):
        if not _TRACEBACK_START.match(lines[i]):
            i += 1
            continue

        block = [lines[i]]
        i += 1
        while i < len(lines) and (
            _FRAME_LINE.match(lines[i])
            or (lines[i].startswith("    ") and not _EXCEPTION_LINE.match(lines[i]))
        ):
            block.append(lines[i])
            i += 1

        exception_type, message = "UnknownError", ""
        if i < len(lines) and (match := _EXCEPTION_LINE.match(lines[i])):
            exception_type, message = match.group(1), match.group(2).strip()
            block.append(lines[i])
            i += 1

        traces.append(
            StackTrace(exception_type=exception_type, message=message, raw_text="\n".join(block))
        )

    return traces


def _normalize_signature(line: str) -> str:
    """Collapse a log line to a signature so near-identical errors (same
    message, different id/timestamp/duration) group together."""
    without_timestamp = _TIMESTAMP_PREFIX_PATTERN.sub("", line)
    return _DIGITS_PATTERN.sub("#", without_timestamp).strip()


def _group_error_lines_by_signature(error_lines: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for line in error_lines:
        groups[_normalize_signature(line)].append(line)
    return groups


def identify_repeated_failures(
    error_lines: list[str], *, min_occurrences: int = _MIN_REPEATED_OCCURRENCES
) -> list[RepeatedFailure]:
    """Group error lines by normalized signature and keep groups seen more than once.

    Grouping by signature (not exact text) means "timed out after 3013ms"
    and "timed out after 4502ms" are recognized as the same recurring
    failure rather than two unrelated one-off errors.
    """
    groups = _group_error_lines_by_signature(error_lines)

    failures = [
        RepeatedFailure(
            signature=signature,
            example_message=occurrences[0],
            count=len(occurrences),
            first_seen=extract_leading_timestamp(occurrences[0]),
            last_seen=extract_leading_timestamp(occurrences[-1]),
        )
        for signature, occurrences in groups.items()
        if len(occurrences) >= min_occurrences
    ]
    return sorted(failures, key=lambda f: f.count, reverse=True)


def _detect_singleton_critical_anomalies(error_lines: list[str]) -> list[str]:
    """A CRITICAL/FATAL line that occurs exactly once is itself anomalous —
    distinct from a recurring pattern, a one-off catastrophic event is
    worth flagging on its own."""
    signature_counts = Counter(_normalize_signature(line) for line in error_lines)

    anomalies = []
    seen_signatures: set[str] = set()
    for line in error_lines:
        if not _CRITICAL_LEVEL_PATTERN.search(line):
            continue
        signature = _normalize_signature(line)
        if signature_counts[signature] == 1 and signature not in seen_signatures:
            seen_signatures.add(signature)
            anomalies.append(f"Isolated critical/fatal event (occurred once): {line}")
    return anomalies


def _detect_error_bursts(error_lines: list[str]) -> list[str]:
    """Flag a burst: `_BURST_MIN_ERRORS`+ errors within a `_BURST_WINDOW_SECONDS` window."""
    timestamps: list[datetime] = []
    for line in error_lines:
        if not (raw := extract_leading_timestamp(line)):
            continue
        try:
            timestamps.append(datetime.fromisoformat(raw))
        except ValueError:
            continue
    timestamps.sort()

    anomalies = []
    window_start = 0
    for window_end in range(len(timestamps)):
        span = (timestamps[window_end] - timestamps[window_start]).total_seconds()
        while span > _BURST_WINDOW_SECONDS:
            window_start += 1
            span = (timestamps[window_end] - timestamps[window_start]).total_seconds()
        count = window_end - window_start + 1
        if count >= _BURST_MIN_ERRORS:
            anomalies.append(
                f"Error burst: {count} errors within {_BURST_WINDOW_SECONDS}s "
                f"({timestamps[window_start].isoformat()} to {timestamps[window_end].isoformat()})"
            )
            break  # one burst anomaly is enough context; avoid repeating for every window

    return anomalies


def detect_anomalies(error_lines: list[str]) -> list[str]:
    """Rule-based anomaly detection over the raw error lines.

    Two concrete rules: an isolated CRITICAL/FATAL event (notable even
    without repetition), and a burst of errors clustered in a short time
    window (notable even if each error looks routine on its own).
    """
    return _detect_singleton_critical_anomalies(error_lines) + _detect_error_bursts(error_lines)


def extract_affected_components(logs: str) -> list[str]:
    """Pull out service/component names mentioned alongside an error or warning level.

    Matches the `LEVEL component-name: message` shape used throughout this
    project's logs (e.g. `ERROR checkout-service: ...`), deduped in the
    order first seen.
    """
    seen: list[str] = []
    for match in _COMPONENT_PATTERN.finditer(logs):
        component = match.group(1)
        if component not in seen:
            seen.append(component)
    return seen


__all__ = [
    "detect_anomalies",
    "extract_affected_components",
    "extract_stack_traces",
    "identify_repeated_failures",
]

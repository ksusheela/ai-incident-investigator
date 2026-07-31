"""A small, curated catalog of common production-incident failure patterns.

Rendered into the Root Cause Agent's system prompt so it can explicitly
match observed evidence (stack traces, repeated failures, anomalies)
against known patterns rather than inventing an explanation from nothing
every time — and so it can just as validly conclude "no known pattern
matches", which is itself useful signal rather than a forced guess.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FailurePattern:
    name: str
    description: str


FAILURE_PATTERN_CATALOG: list[FailurePattern] = [
    FailurePattern(
        name="connection_pool_exhaustion",
        description=(
            "Repeated connection timeouts to the same downstream dependency, often under "
            "load, as a connection pool runs out of available connections."
        ),
    ),
    FailurePattern(
        name="cascading_timeout",
        description=(
            "A slow downstream dependency causes timeouts to propagate upward through "
            "several services."
        ),
    ),
    FailurePattern(
        name="resource_exhaustion",
        description=(
            "Out-of-memory, disk-full, or file-descriptor-exhaustion errors, often preceded "
            "by gradually increasing resource usage."
        ),
    ),
    FailurePattern(
        name="null_reference",
        description=(
            "NoneType/NullPointer-style exceptions from unexpected missing or malformed data."
        ),
    ),
    FailurePattern(
        name="deadlock_or_contention",
        description=(
            "Requests hang or time out waiting on a shared lock/resource, with no explicit "
            "error until a timeout fires."
        ),
    ),
    FailurePattern(
        name="configuration_error",
        description=(
            "Errors immediately after a deploy or config change, often about missing or "
            "invalid settings or credentials."
        ),
    ),
    FailurePattern(
        name="dependency_outage",
        description=(
            "A single external dependency fails uniformly across many otherwise-unrelated "
            "requests."
        ),
    ),
    FailurePattern(
        name="traffic_spike",
        description=(
            "Errors correlate with a sudden increase in request volume rather than a code "
            "or infrastructure defect."
        ),
    ),
]

KNOWN_PATTERN_NAMES = frozenset(pattern.name for pattern in FAILURE_PATTERN_CATALOG)


def render_catalog_for_prompt() -> str:
    """Render the catalog as a bullet list for embedding in a prompt."""
    return "\n".join(
        f"- {pattern.name}: {pattern.description}" for pattern in FAILURE_PATTERN_CATALOG
    )


__all__ = [
    "FAILURE_PATTERN_CATALOG",
    "KNOWN_PATTERN_NAMES",
    "FailurePattern",
    "render_catalog_for_prompt",
]

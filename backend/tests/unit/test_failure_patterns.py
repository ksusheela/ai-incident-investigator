"""Unit tests for the known-failure-pattern catalog."""

from app.agents.nodes.failure_patterns import (
    FAILURE_PATTERN_CATALOG,
    KNOWN_PATTERN_NAMES,
    render_catalog_for_prompt,
)


def test_catalog_is_non_empty():
    assert len(FAILURE_PATTERN_CATALOG) > 0


def test_every_pattern_has_a_unique_name_and_description():
    names = [pattern.name for pattern in FAILURE_PATTERN_CATALOG]

    assert len(names) == len(set(names))
    assert all(pattern.description.strip() for pattern in FAILURE_PATTERN_CATALOG)


def test_known_pattern_names_matches_the_catalog():
    assert KNOWN_PATTERN_NAMES == {pattern.name for pattern in FAILURE_PATTERN_CATALOG}


def test_rendered_catalog_includes_every_pattern_name():
    rendered = render_catalog_for_prompt()

    for pattern in FAILURE_PATTERN_CATALOG:
        assert pattern.name in rendered

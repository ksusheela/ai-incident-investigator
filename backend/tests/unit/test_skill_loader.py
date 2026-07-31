"""Unit tests for SKILL.md parsing and the SkillLoader."""

import pytest
from pydantic import ValidationError

from app.agents.skills.loader import SkillLoader, SkillLoadError
from app.agents.skills.models import Skill, SkillMetadata, SkillTriggers
from app.agents.skills.parser import SkillParseError, parse_skill_markdown

VALID_SKILL_MD = """\
---
name: example
version: 1.0.0
description: An example skill for testing.
triggers:
  keywords:
    - "boom"
  patterns:
    - "\\\\bboom\\\\b"
---

# Example

## When this applies

When the logs say "boom".

## Guidance

Investigate the boom.

## Examples

**Input:** `boom`
**Guidance applied:** it went boom.
"""


def test_parse_skill_markdown_splits_front_matter_and_body():
    metadata, body = parse_skill_markdown(VALID_SKILL_MD)

    assert metadata["name"] == "example"
    assert metadata["version"] == "1.0.0"
    assert body.startswith("# Example")
    assert "## Examples" in body


def test_parse_skill_markdown_rejects_missing_front_matter():
    with pytest.raises(SkillParseError):
        parse_skill_markdown("# Just a heading, no front matter\n\n## Examples\nx")


def test_parse_skill_markdown_rejects_invalid_yaml():
    text = "---\nname: [unterminated\n---\n\nbody\n\n## Examples\nx"
    with pytest.raises(SkillParseError):
        parse_skill_markdown(text)


def test_parse_skill_markdown_requires_examples_section():
    text = "---\nname: x\nversion: 1.0.0\ndescription: d\n---\n\n# X\n\nNo examples here."
    with pytest.raises(SkillParseError):
        parse_skill_markdown(text)


def test_skill_metadata_rejects_malformed_version():
    with pytest.raises(ValidationError):
        SkillMetadata(name="x", version="1.0", description="d")


def test_skill_metadata_version_tuple():
    metadata = SkillMetadata(name="x", version="1.2.3", description="d")

    assert metadata.version_tuple == (1, 2, 3)


def _skill(name: str, version: str, *, keywords: list[str] | None = None) -> Skill:
    return Skill(
        metadata=SkillMetadata(
            name=name,
            version=version,
            description="test skill",
            triggers=SkillTriggers(keywords=keywords or []),
        ),
        content="body content\n\n## Examples\nx",
        source_path=f"<test:{name}:{version}>",
    )


def test_loader_from_skills_matches_by_keyword():
    loader = SkillLoader.from_skills([_skill("python", "1.0.0", keywords=["Traceback"])])

    assert [s.metadata.name for s in loader.match("Traceback (most recent call last):")] == [
        "python"
    ]
    assert loader.match("nothing relevant here") == []


def test_loader_higher_version_wins_on_name_conflict():
    loader = SkillLoader.from_skills([_skill("python", "1.0.0"), _skill("python", "2.0.0")])

    assert loader.get("python").metadata.version == "2.0.0"
    assert len(loader.shadowed_skills) == 1
    assert "1.0.0" in loader.shadowed_skills[0]


def test_loader_records_shadowed_skill_regardless_of_load_order():
    loader = SkillLoader.from_skills([_skill("python", "2.0.0"), _skill("python", "1.0.0")])

    assert loader.get("python").metadata.version == "2.0.0"
    assert len(loader.shadowed_skills) == 1


def test_loader_all_skills_returns_every_distinct_name():
    loader = SkillLoader.from_skills([_skill("python", "1.0.0"), _skill("fastapi", "1.0.0")])

    names = {s.metadata.name for s in loader.all_skills()}
    assert names == {"python", "fastapi"}


def test_loader_raises_skill_load_error_for_malformed_file(tmp_path):
    skill_dir = tmp_path / "broken"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("not a valid skill file at all", encoding="utf-8")

    loader = SkillLoader(skills_dir=tmp_path)

    with pytest.raises(SkillLoadError):
        loader.load()


def test_loader_loads_the_real_bundled_skill_library():
    """The three bundled example skills (python, fastapi, log_analysis)
    must all parse, validate, and be individually addressable."""
    loader = SkillLoader()
    loader.load()

    names = {s.metadata.name for s in loader.all_skills()}
    assert names == {"python", "fastapi", "log_analysis"}
    assert loader.shadowed_skills == []

    for skill in loader.all_skills():
        assert skill.metadata.version_tuple  # valid semver, already parsed
        assert skill.metadata.description
        assert "## Examples" in skill.content


def test_bundled_python_skill_matches_a_real_traceback():
    loader = SkillLoader()
    loader.load()

    logs = (
        "Traceback (most recent call last):\n"
        '  File "app.py", line 1, in <module>\n'
        "ZeroDivisionError: division by zero"
    )
    matched_names = {s.metadata.name for s in loader.match(logs)}

    assert "python" in matched_names


def test_bundled_skills_do_not_match_clean_logs():
    loader = SkillLoader()
    loader.load()

    assert loader.match("2026-07-31T10:00:00Z INFO checkout-service: request handled") == []

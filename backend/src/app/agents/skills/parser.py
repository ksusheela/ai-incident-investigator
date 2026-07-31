"""Parses the SKILL.md format: YAML front matter + Markdown body.

    ---
    name: example
    version: 1.0.0
    description: ...
    triggers:
      keywords: [...]
      patterns: [...]
    ---

    # Markdown body (the actual guidance)...
"""

import re

import yaml

_FRONT_MATTER_PATTERN = re.compile(r"^---[ \t]*\n(.*?\n)---[ \t]*\n(.*)$", re.DOTALL)

REQUIRED_BODY_SECTION = "## Examples"


class SkillParseError(RuntimeError):
    """Raised when a SKILL.md file doesn't match the expected format."""


def parse_skill_markdown(text: str) -> tuple[dict, str]:
    """Split `text` into its front-matter metadata dict and Markdown body.

    Requires an `## Examples` section in the body — every skill must
    document at least one worked example, not just abstract guidance.
    """
    match = _FRONT_MATTER_PATTERN.match(text)
    if not match:
        raise SkillParseError(
            "SKILL.md must start with YAML front matter delimited by '---' lines"
        )

    front_matter_yaml, body = match.groups()
    try:
        metadata = yaml.safe_load(front_matter_yaml)
    except yaml.YAMLError as exc:
        raise SkillParseError(f"Invalid YAML front matter: {exc}") from exc

    if not isinstance(metadata, dict):
        raise SkillParseError("SKILL.md front matter must be a YAML mapping")

    body = body.strip()
    if not body:
        raise SkillParseError("SKILL.md has no body content below the front matter")
    if REQUIRED_BODY_SECTION not in body:
        raise SkillParseError(f"SKILL.md body must include a {REQUIRED_BODY_SECTION!r} section")

    return metadata, body


__all__ = ["REQUIRED_BODY_SECTION", "SkillParseError", "parse_skill_markdown"]

"""Discovers, parses, validates, and matches Agent Skills.

Skills live one per directory under `library/`, e.g.
`library/python/SKILL.md`. Discovery is by directory, not filename, so a
future skill can ship supporting files (e.g. reference data) alongside
its SKILL.md without the loader needing to know about them.
"""

import re
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from app.agents.skills.models import Skill, SkillMetadata
from app.agents.skills.parser import SkillParseError, parse_skill_markdown

DEFAULT_SKILLS_DIR = Path(__file__).parent / "library"


class SkillLoadError(RuntimeError):
    """Raised when a SKILL.md file fails to parse or validate."""


class SkillLoader:
    """Loads every SKILL.md under a directory and matches them against log text.

    If two skill files declare the same `name`, the higher `version` wins;
    the loser is recorded (not silently discarded) and available via
    `shadowed_skills` for diagnostics.
    """

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._skills_dir = skills_dir or DEFAULT_SKILLS_DIR
        self._skills: dict[str, Skill] = {}
        self._shadowed: list[str] = []
        self._loaded = False

    @classmethod
    def from_skills(cls, skills: list[Skill]) -> "SkillLoader":
        """Build a loader from already-constructed skills, bypassing disk I/O.

        Used by tests that want to control exactly which skills are
        available without depending on the bundled `library/` contents.
        """
        loader = cls()
        for skill in skills:
            loader._register(skill)
        loader._loaded = True
        return loader

    def load(self) -> None:
        """Discover and parse every `*/SKILL.md` under the skills directory."""
        for skill_file in sorted(self._skills_dir.glob("*/SKILL.md")):
            self._register(self._read_one(skill_file))
        self._loaded = True

    def _read_one(self, path: Path) -> Skill:
        text = path.read_text(encoding="utf-8")
        try:
            metadata_dict, content = parse_skill_markdown(text)
            metadata = SkillMetadata.model_validate(metadata_dict)
        except (SkillParseError, ValidationError) as exc:
            raise SkillLoadError(f"Failed to load skill from {path}: {exc}") from exc
        return Skill(metadata=metadata, content=content, source_path=str(path))

    def _register(self, skill: Skill) -> None:
        existing = self._skills.get(skill.metadata.name)
        if existing is None:
            self._skills[skill.metadata.name] = skill
            return

        incoming_is_newer = skill.metadata.version_tuple > existing.metadata.version_tuple
        winner, loser = (skill, existing) if incoming_is_newer else (existing, skill)
        self._skills[skill.metadata.name] = winner
        self._shadowed.append(
            f"{loser.source_path} (v{loser.metadata.version}) shadowed by "
            f"{winner.source_path} (v{winner.metadata.version})"
        )

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def all_skills(self) -> list[Skill]:
        self._ensure_loaded()
        return list(self._skills.values())

    def get(self, name: str) -> Skill | None:
        self._ensure_loaded()
        return self._skills.get(name)

    def match(self, text: str) -> list[Skill]:
        """Return every skill whose trigger conditions match `text`."""
        self._ensure_loaded()
        return [skill for skill in self._skills.values() if _skill_matches(skill, text)]

    @property
    def shadowed_skills(self) -> list[str]:
        self._ensure_loaded()
        return list(self._shadowed)


def _skill_matches(skill: Skill, text: str) -> bool:
    triggers = skill.metadata.triggers
    lowered = text.lower()
    if any(keyword.lower() in lowered for keyword in triggers.keywords):
        return True
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in triggers.patterns)


@lru_cache
def get_skill_loader() -> SkillLoader:
    """FastAPI dependency: the process-wide cached, lazily-loaded skill library."""
    loader = SkillLoader()
    loader.load()
    return loader

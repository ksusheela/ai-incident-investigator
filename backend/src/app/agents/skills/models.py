"""Data model for a loaded Agent Skill.

A Skill is a bundle of domain expertise (Markdown guidance) that agents
can pull into their prompts when its trigger conditions match the logs
under investigation — the same idea as this project's own coding-agent
skills, applied to the incident-investigation pipeline itself.
"""

import re

from pydantic import BaseModel, Field, field_validator

_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


class SkillTriggers(BaseModel):
    """Conditions under which a skill is considered relevant to a log excerpt.

    A skill matches if ANY keyword is found (case-insensitive substring)
    OR any pattern matches (regex search) against the log text.
    """

    keywords: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)


class SkillMetadata(BaseModel):
    """Front-matter metadata declared at the top of a SKILL.md file."""

    name: str
    version: str
    description: str
    author: str = "AI Incident Investigator"
    triggers: SkillTriggers = Field(default_factory=SkillTriggers)

    @field_validator("version")
    @classmethod
    def _validate_semver(cls, value: str) -> str:
        if not _VERSION_PATTERN.match(value):
            raise ValueError(f"version {value!r} must be in MAJOR.MINOR.PATCH form (e.g. '1.0.0')")
        return value

    @property
    def version_tuple(self) -> tuple[int, int, int]:
        major, minor, patch = self.version.split(".")
        return int(major), int(minor), int(patch)


class Skill(BaseModel):
    """A fully loaded, validated skill: metadata + Markdown guidance body."""

    metadata: SkillMetadata
    content: str
    source_path: str

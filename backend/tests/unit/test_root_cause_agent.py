"""Unit tests for the Root Cause Agent, isolated from the rest of the graph."""

import json

import pytest

from app.agents.errors import AgentOutputError
from app.agents.nodes.root_cause_agent import make_root_cause_agent
from app.agents.skills.loader import SkillLoader
from app.agents.skills.models import Skill, SkillMetadata, SkillTriggers
from app.agents.state.investigation_state import InvestigationState, LogAnalysisResult
from tests.fakes import FakeLLMProvider

LOG_ANALYSIS = LogAnalysisResult(
    affected_components=["payments-db"],
    time_range="2026-07-31T14:02:00 to 2026-07-31T14:02:10",
    stack_traces=[],
    repeated_failures=[],
    anomalies=[],
)

EMPTY_SKILL_LOADER = SkillLoader.from_skills([])

_VALID_RESPONSE = json.dumps(
    {
        "hypothesis": "connection pool exhaustion",
        "matched_pattern": "connection_pool_exhaustion",
        "confidence_score": 0.9,
        "reasoning": "Repeated timeouts under load.",
        "contributing_factors": [],
    }
)


def _state_with_log_analysis(logs: str = "irrelevant") -> InvestigationState:
    return InvestigationState(logs=logs, log_analysis=LOG_ANALYSIS)


async def test_accepts_a_valid_matched_pattern():
    llm = FakeLLMProvider(responses=[_VALID_RESPONSE])
    agent = make_root_cause_agent(llm, EMPTY_SKILL_LOADER)

    update = await agent(_state_with_log_analysis())

    assert update["root_cause"].matched_pattern == "connection_pool_exhaustion"
    assert update["root_cause"].confidence_score == 0.9


async def test_accepts_null_matched_pattern_for_a_novel_failure():
    llm = FakeLLMProvider(
        responses=[
            json.dumps(
                {
                    "hypothesis": "something not in the catalog",
                    "matched_pattern": None,
                    "confidence_score": 0.4,
                    "reasoning": "No known pattern clearly applies.",
                    "contributing_factors": [],
                }
            )
        ]
    )
    agent = make_root_cause_agent(llm, EMPTY_SKILL_LOADER)

    update = await agent(_state_with_log_analysis())

    assert update["root_cause"].matched_pattern is None


async def test_rejects_a_matched_pattern_not_in_the_catalog():
    llm = FakeLLMProvider(
        responses=[
            json.dumps(
                {
                    "hypothesis": "something",
                    "matched_pattern": "not_a_real_pattern",
                    "confidence_score": 0.5,
                    "reasoning": "irrelevant",
                    "contributing_factors": [],
                }
            )
        ]
    )
    agent = make_root_cause_agent(llm, EMPTY_SKILL_LOADER)

    with pytest.raises(AgentOutputError):
        await agent(_state_with_log_analysis())


async def test_rejects_confidence_score_out_of_range():
    llm = FakeLLMProvider(
        responses=[
            json.dumps(
                {
                    "hypothesis": "something",
                    "matched_pattern": None,
                    "confidence_score": 1.5,
                    "reasoning": "irrelevant",
                    "contributing_factors": [],
                }
            )
        ]
    )
    agent = make_root_cause_agent(llm, EMPTY_SKILL_LOADER)

    with pytest.raises(AgentOutputError):
        await agent(_state_with_log_analysis())


async def test_rejects_missing_reasoning_field():
    llm = FakeLLMProvider(
        responses=[
            json.dumps(
                {
                    "hypothesis": "something",
                    "matched_pattern": None,
                    "confidence_score": 0.5,
                    "contributing_factors": [],
                }
            )
        ]
    )
    agent = make_root_cause_agent(llm, EMPTY_SKILL_LOADER)

    with pytest.raises(AgentOutputError):
        await agent(_state_with_log_analysis())


async def test_matched_skill_content_is_appended_to_the_prompt():
    skill_loader = SkillLoader.from_skills(
        [
            Skill(
                metadata=SkillMetadata(
                    name="python",
                    version="1.0.0",
                    description="test",
                    triggers=SkillTriggers(keywords=["Traceback"]),
                ),
                content="Distinctive python guidance text.\n\n## Examples\nx",
                source_path="<test>",
            )
        ]
    )
    llm = FakeLLMProvider(responses=[_VALID_RESPONSE])
    agent = make_root_cause_agent(llm, skill_loader)

    await agent(_state_with_log_analysis(logs="Traceback (most recent call last):\nx"))

    _system, prompt = llm.calls[0]
    assert "Distinctive python guidance text." in prompt


async def test_no_matched_skill_means_no_extra_prompt_content():
    skill_loader = SkillLoader.from_skills(
        [
            Skill(
                metadata=SkillMetadata(
                    name="python",
                    version="1.0.0",
                    description="test",
                    triggers=SkillTriggers(keywords=["Traceback"]),
                ),
                content="Distinctive python guidance text.\n\n## Examples\nx",
                source_path="<test>",
            )
        ]
    )
    llm = FakeLLMProvider(responses=[_VALID_RESPONSE])
    agent = make_root_cause_agent(llm, skill_loader)

    await agent(_state_with_log_analysis(logs="nothing relevant here"))

    _system, prompt = llm.calls[0]
    assert "Distinctive python guidance text." not in prompt

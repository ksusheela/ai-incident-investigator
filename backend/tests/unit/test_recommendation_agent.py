"""Unit tests for the Recommendation Agent, isolated from the rest of the graph."""

import json

import pytest

from app.agents.errors import AgentOutputError
from app.agents.nodes.recommendation_agent import make_recommendation_agent
from app.agents.state.investigation_state import InvestigationState, RootCauseResult
from tests.fakes import FakeLLMProvider

ROOT_CAUSE = RootCauseResult(
    hypothesis="payments-db connection pool exhaustion",
    matched_pattern="connection_pool_exhaustion",
    confidence_score=0.85,
    reasoning="Repeated timeouts under load.",
    contributing_factors=["undersized connection pool"],
)


def _state_with_root_cause() -> InvestigationState:
    return InvestigationState(logs="irrelevant", root_cause=ROOT_CAUSE)


async def test_accepts_recommendations_across_all_three_categories():
    llm = FakeLLMProvider(
        responses=[
            json.dumps(
                {
                    "code_fixes": [
                        {
                            "description": "Add retry with backoff",
                            "rationale": "Reduces spurious failures.",
                        }
                    ],
                    "configuration_changes": [
                        {"description": "Increase pool size", "rationale": "Pool is undersized."}
                    ],
                    "database_improvements": [
                        {"description": "Add read replica", "rationale": "Offloads read traffic."}
                    ],
                }
            )
        ]
    )
    agent = make_recommendation_agent(llm)

    update = await agent(_state_with_root_cause())

    result = update["recommendations"]
    assert len(result.code_fixes) == 1
    assert len(result.configuration_changes) == 1
    assert len(result.database_improvements) == 1
    assert result.code_fixes[0].rationale == "Reduces spurious failures."


async def test_accepts_empty_categories_that_do_not_apply():
    llm = FakeLLMProvider(
        responses=[
            json.dumps(
                {
                    "code_fixes": [],
                    "configuration_changes": [
                        {"description": "Increase pool size", "rationale": "Pool is undersized."}
                    ],
                    "database_improvements": [],
                }
            )
        ]
    )
    agent = make_recommendation_agent(llm)

    update = await agent(_state_with_root_cause())

    assert update["recommendations"].code_fixes == []
    assert update["recommendations"].database_improvements == []


async def test_rejects_all_categories_empty():
    llm = FakeLLMProvider(
        responses=[
            json.dumps({"code_fixes": [], "configuration_changes": [], "database_improvements": []})
        ]
    )
    agent = make_recommendation_agent(llm)

    with pytest.raises(AgentOutputError):
        await agent(_state_with_root_cause())


async def test_rejects_recommendation_missing_rationale():
    llm = FakeLLMProvider(
        responses=[
            json.dumps(
                {
                    "code_fixes": [{"description": "Add retry with backoff"}],
                    "configuration_changes": [],
                    "database_improvements": [],
                }
            )
        ]
    )
    agent = make_recommendation_agent(llm)

    with pytest.raises(AgentOutputError):
        await agent(_state_with_root_cause())


async def test_rejects_unparseable_output():
    llm = FakeLLMProvider(responses=["not json at all"])
    agent = make_recommendation_agent(llm)

    with pytest.raises(AgentOutputError):
        await agent(_state_with_root_cause())

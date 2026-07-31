"""Recommendation Agent — suggests concrete code, configuration, and
database fixes for the confirmed root cause, each with its rationale."""

import json
from collections.abc import Awaitable, Callable

from pydantic import ValidationError

from app.agents.errors import AgentOutputError
from app.agents.prompts.investigation_prompts import (
    RECOMMENDATION_SYSTEM_PROMPT,
    build_recommendation_prompt,
)
from app.agents.state.investigation_state import InvestigationState, RecommendationResult
from app.infrastructure.llm.provider import LLMProvider

AGENT_NAME = "Recommendation Agent"


def make_recommendation_agent(llm: LLMProvider) -> Callable[[InvestigationState], Awaitable[dict]]:
    async def recommendation_agent(state: InvestigationState) -> dict:
        assert state.root_cause is not None, "recommendation_agent requires root_cause"

        raw = await llm.complete(
            system=RECOMMENDATION_SYSTEM_PROMPT,
            prompt=build_recommendation_prompt(root_cause=state.root_cause),
        )
        try:
            result = RecommendationResult.model_validate(json.loads(raw))
            total_recommendations = (
                len(result.code_fixes)
                + len(result.configuration_changes)
                + len(result.database_improvements)
            )
            if total_recommendations == 0:
                raise ValueError("no recommendations produced for a confirmed root cause")
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise AgentOutputError(AGENT_NAME, raw, exc) from exc

        return {"recommendations": result}

    return recommendation_agent

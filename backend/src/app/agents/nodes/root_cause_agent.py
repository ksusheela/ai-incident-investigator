"""Root Cause Agent — analyzes stack traces and other log-analysis evidence
to hypothesize why the incident happened, with a confidence score and
explained reasoning.

Unlike Monitoring and Log Analysis, this genuinely needs LLM judgment —
matching evidence to a plausible explanation and weighing how strongly it
supports that explanation isn't a mechanical parsing task.
"""

import json
from collections.abc import Awaitable, Callable

from pydantic import ValidationError

from app.agents.errors import AgentOutputError
from app.agents.nodes.failure_patterns import KNOWN_PATTERN_NAMES
from app.agents.prompts.investigation_prompts import (
    ROOT_CAUSE_SYSTEM_PROMPT,
    build_root_cause_prompt,
)
from app.agents.state.investigation_state import InvestigationState, RootCauseResult
from app.infrastructure.llm.provider import LLMProvider

AGENT_NAME = "Root Cause Agent"


def make_root_cause_agent(llm: LLMProvider) -> Callable[[InvestigationState], Awaitable[dict]]:
    async def root_cause_agent(state: InvestigationState) -> dict:
        assert state.log_analysis is not None, "root_cause_agent requires log_analysis"

        raw = await llm.complete(
            system=ROOT_CAUSE_SYSTEM_PROMPT,
            prompt=build_root_cause_prompt(log_analysis=state.log_analysis),
        )
        try:
            result = RootCauseResult.model_validate(json.loads(raw))
            is_unknown_pattern = (
                result.matched_pattern is not None
                and result.matched_pattern not in KNOWN_PATTERN_NAMES
            )
            if is_unknown_pattern:
                raise ValueError(
                    f"matched_pattern {result.matched_pattern!r} is not in the known catalog"
                )
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise AgentOutputError(AGENT_NAME, raw, exc) from exc

        return {"root_cause": result}

    return root_cause_agent

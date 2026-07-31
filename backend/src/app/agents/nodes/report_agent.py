"""Report Agent — synthesizes every prior finding into a professional
Markdown incident report (Summary, Root Cause, Evidence, Confidence,
Recommendation, Next Steps).

Only Summary and Next Steps are LLM-authored; the rest is rendered
deterministically from already-validated state — see `report_renderer.py`
for why.
"""

import json
from collections.abc import Awaitable, Callable

from pydantic import ValidationError

from app.agents.errors import AgentOutputError
from app.agents.nodes.report_renderer import render_incident_report_markdown
from app.agents.prompts.investigation_prompts import REPORT_SYSTEM_PROMPT, build_report_prompt
from app.agents.state.investigation_state import InvestigationState, ReportSections
from app.infrastructure.llm.provider import LLMProvider

AGENT_NAME = "Report Agent"


def make_report_agent(llm: LLMProvider) -> Callable[[InvestigationState], Awaitable[dict]]:
    async def report_agent(state: InvestigationState) -> dict:
        assert state.log_analysis is not None, "report_agent requires log_analysis"
        assert state.root_cause is not None, "report_agent requires root_cause"
        assert state.recommendations is not None, "report_agent requires recommendations"

        raw = await llm.complete(
            system=REPORT_SYSTEM_PROMPT,
            prompt=build_report_prompt(
                monitoring_summary=state.monitoring.summary if state.monitoring else "",
                log_analysis=state.log_analysis,
                root_cause=state.root_cause,
                recommendations=state.recommendations,
            ),
        )
        try:
            sections = ReportSections.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AgentOutputError(AGENT_NAME, raw, exc) from exc

        report = render_incident_report_markdown(state, sections)
        return {"report": report}

    return report_agent

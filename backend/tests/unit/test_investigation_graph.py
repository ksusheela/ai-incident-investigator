"""Unit tests for the LangGraph incident-investigation orchestrator."""

import json

import pytest

from app.agents.errors import AgentOutputError
from app.agents.graphs.investigation_graph import build_investigation_graph
from app.agents.skills.loader import SkillLoader
from app.agents.state.investigation_state import InvestigationState
from tests.fakes import FakeLLMProvider

CLEAN_LOGS = "2026-07-31T10:00:00Z INFO checkout-service: request handled in 12ms"
INCIDENT_LOGS = (
    "2026-07-31T14:02:00Z ERROR checkout-service: 500 Internal Server Error\n"
    "2026-07-31T14:02:05Z ERROR checkout-service: connection to payments-db timed out"
)

# The real bundled skill library — these graph-level tests use it as-is to
# demonstrate genuine end-to-end integration; skill-specific behavior
# (matching, prompt augmentation) has its own focused tests in
# test_skill_loader.py and test_root_cause_agent.py.
SKILL_LOADER = SkillLoader()


async def test_stops_after_monitoring_when_no_incident_detected():
    llm = FakeLLMProvider(responses=[])  # no LLM-backed agent should run
    graph = build_investigation_graph(llm, SKILL_LOADER)

    result = await graph.ainvoke(InvestigationState(logs=CLEAN_LOGS))
    state = InvestigationState.model_validate(result)

    assert state.monitoring.incident_detected is False
    assert state.monitoring.severity == "none"
    assert state.log_analysis is None
    assert state.root_cause is None
    assert state.recommendations is None
    assert state.report is None
    assert len(llm.calls) == 0


async def test_runs_full_pipeline_when_incident_detected():
    responses = [
        json.dumps(
            {
                "hypothesis": "payments-db connection pool exhaustion",
                "matched_pattern": "connection_pool_exhaustion",
                "confidence_score": 0.85,
                "reasoning": "Repeated timeouts to payments-db under load match this pattern.",
                "contributing_factors": ["undersized connection pool", "traffic spike"],
            }
        ),
        json.dumps(
            {
                "code_fixes": [],
                "configuration_changes": [
                    {
                        "description": "Increase payments-db connection pool size",
                        "rationale": "Repeated timeouts under load indicate an undersized pool.",
                    }
                ],
                "database_improvements": [
                    {
                        "description": "Add connection pool autoscaling to payments-db",
                        "rationale": "Prevents recurrence as traffic grows further.",
                    }
                ],
            }
        ),
        json.dumps(
            {
                "summary": "Checkout requests failed repeatedly due to payments-db timeouts.",
                "next_steps": ["Notify the payments team", "Schedule a postmortem"],
            }
        ),
    ]
    llm = FakeLLMProvider(responses=responses)
    graph = build_investigation_graph(llm, SKILL_LOADER)

    result = await graph.ainvoke(InvestigationState(logs=INCIDENT_LOGS))
    state = InvestigationState.model_validate(result)

    assert state.monitoring.incident_detected is True
    assert state.monitoring.error_count == 2
    assert state.monitoring.severity == "medium"
    # Log Analysis is deterministic (see test_log_analyzer.py for its own
    # dedicated tests) — just confirm it ran and populated the state.
    assert state.log_analysis.affected_components == ["checkout-service"]
    assert state.root_cause.hypothesis == "payments-db connection pool exhaustion"
    assert state.root_cause.matched_pattern == "connection_pool_exhaustion"
    assert state.root_cause.confidence_score == 0.85
    assert state.recommendations.code_fixes == []
    assert (
        "connection pool size" in state.recommendations.configuration_changes[0].description
    )
    assert state.report.startswith("# Incident Report")
    required_headings = (
        "## Summary",
        "## Root Cause",
        "## Evidence",
        "## Confidence",
        "## Recommendation",
        "## Next Steps",
    )
    for heading in required_headings:
        assert heading in state.report
    assert "Notify the payments team" in state.report
    assert "85% (High)" in state.report
    assert len(llm.calls) == 3


async def test_root_cause_agent_raises_on_unparseable_output():
    llm = FakeLLMProvider(responses=["not json at all"])
    graph = build_investigation_graph(llm, SKILL_LOADER)

    with pytest.raises(AgentOutputError):
        await graph.ainvoke(InvestigationState(logs=INCIDENT_LOGS))

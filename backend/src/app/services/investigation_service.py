"""Application/use-case layer for running an incident investigation."""

import time
from functools import partial

import anyio

from app.agents.graphs.investigation_graph import build_investigation_graph
from app.agents.skills.loader import SkillLoader
from app.agents.state.investigation_state import InvestigationState
from app.evaluation.evaluator import evaluate_investigation
from app.infrastructure.filesystem.artifact_store import IncidentArtifactStore
from app.infrastructure.llm.provider import LLMProvider


async def run_investigation(
    *,
    logs: str,
    llm: LLMProvider,
    skill_loader: SkillLoader,
    artifact_store: IncidentArtifactStore,
) -> InvestigationState:
    """Run the full investigation pipeline over `logs` and return the final state.

    Confirmed incidents (`monitoring.incident_detected`) are persisted to
    `artifact_store` — the raw log, the full state, and the report if one
    was produced — and the returned state's `incident_id` is populated to
    match. The investigation is also evaluated (response time, confidence,
    root-cause/recommendation quality) and that evaluation persisted
    alongside it, feeding the dashboard's evaluation summary. Clean logs
    are never persisted or evaluated; there's nothing worth keeping.
    """
    start_time = time.perf_counter()
    graph = build_investigation_graph(llm, skill_loader)
    result = await graph.ainvoke(InvestigationState(logs=logs))
    response_time_seconds = time.perf_counter() - start_time
    state = InvestigationState.model_validate(result)

    if state.monitoring and state.monitoring.incident_detected:
        incident_id = await anyio.to_thread.run_sync(
            partial(artifact_store.save_incident, logs=logs, state=state)
        )
        state = state.model_copy(update={"incident_id": incident_id})

        evaluation = evaluate_investigation(
            state=state, response_time_seconds=response_time_seconds
        )
        await anyio.to_thread.run_sync(
            partial(artifact_store.save_evaluation, incident_id, evaluation)
        )

    return state

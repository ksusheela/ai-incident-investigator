"""Evaluation summary endpoint — aggregate metrics for the dashboard.

No LLM dependency: this only reads evaluation records already computed
and persisted during past investigations (see
`services/investigation_service.py`); it never runs a new LLM call itself.
"""

import anyio
from fastapi import APIRouter, Depends

from app.api.common import translate_to_404
from app.evaluation.evaluator import summarize_evaluations
from app.evaluation.models import EvaluationResult, EvaluationSummary
from app.infrastructure.filesystem.artifact_store import IncidentArtifactStore, get_artifact_store

router = APIRouter(tags=["evaluation"])


@router.get("/evaluations/summary", response_model=EvaluationSummary)
async def get_evaluation_summary(
    artifact_store: IncidentArtifactStore = Depends(get_artifact_store),
) -> EvaluationSummary:
    """Aggregate response time, confidence, and quality-rubric scores across
    every confirmed incident evaluated so far."""
    evaluations = await anyio.to_thread.run_sync(artifact_store.list_evaluations)
    return summarize_evaluations(evaluations)


@router.get("/evaluations", response_model=list[EvaluationResult])
async def list_evaluations(
    artifact_store: IncidentArtifactStore = Depends(get_artifact_store),
) -> list[EvaluationResult]:
    """List every stored evaluation, most recently evaluated first.

    Registered after `/evaluations/summary` — that literal route must be
    matched before the `/evaluations/{incident_id}` path-param route
    below, and FastAPI/Starlette match routes in registration order.
    """
    return await anyio.to_thread.run_sync(artifact_store.list_evaluations)


@router.get("/evaluations/{incident_id}", response_model=EvaluationResult)
async def get_evaluation(
    incident_id: str,
    artifact_store: IncidentArtifactStore = Depends(get_artifact_store),
) -> EvaluationResult:
    """Return one incident's evaluation (response time, confidence, quality scores)."""
    with translate_to_404("No evaluation stored for this incident."):
        return await anyio.to_thread.run_sync(artifact_store.read_evaluation, incident_id)

"""Incident listing endpoints — read-only views over persisted artifacts.

Separate from `investigations.py` (which runs new analyses) and
`evaluations.py` (which scores them): this router exposes what
`IncidentArtifactStore` already persisted, over plain REST.

The Filesystem MCP server (`/mcp`) exposes the same underlying data
(`list_incidents`, a report-reading tool) via JSON-RPC tool calls, but
that transport is designed for AI-agent clients, not a browser's
`fetch()` — a real frontend dashboard needs a normal REST surface to list
and revisit past incidents, so this router adds one rather than routing
UI traffic through MCP.
"""

import anyio
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from app.agents.state.investigation_state import Severity
from app.api.common import translate_to_404
from app.infrastructure.filesystem.artifact_store import IncidentArtifactStore, get_artifact_store

router = APIRouter(tags=["incidents"])


class IncidentSummary(BaseModel):
    """One stored incident's headline metadata, for listing."""

    incident_id: str
    created_at: str
    severity: Severity
    summary: str


@router.get("/incidents", response_model=list[IncidentSummary])
async def list_incidents(
    artifact_store: IncidentArtifactStore = Depends(get_artifact_store),
) -> list[IncidentSummary]:
    """List confirmed incidents, most recently created first."""
    records = await anyio.to_thread.run_sync(artifact_store.list_incidents)
    return [
        IncidentSummary(
            incident_id=record.incident_id,
            created_at=record.created_at,
            severity=record.severity,
            summary=record.summary,
        )
        for record in records
    ]


@router.get(
    "/incidents/{incident_id}/report",
    response_class=Response,
    responses={200: {"content": {"text/markdown": {}}}, 404: {"description": "No report stored"}},
)
async def get_incident_report(
    incident_id: str,
    artifact_store: IncidentArtifactStore = Depends(get_artifact_store),
) -> Response:
    """Return the persisted Markdown report for one incident, if any."""
    with translate_to_404("No report stored for this incident."):
        report = await anyio.to_thread.run_sync(artifact_store.read_report, incident_id)
    return Response(content=report, media_type="text/markdown")

"""Incident investigation endpoints — run the LangGraph agent pipeline.

Two ways in: raw log text (`POST /investigations`) or an uploaded log file
(`POST /investigations/upload`). Both translate their input into plain
`logs: str` and delegate to the same `run_investigation()` service call —
the upload endpoint's only job is HTTP-specific concerns (size limit,
encoding) that don't belong in application logic.

Each also has an `/export` counterpart that runs the same pipeline but
returns just the final Markdown report as a downloadable file
(`text/markdown`, `Content-Disposition: attachment`) instead of the full
JSON state — for a human who wants the report itself, not the underlying
data.

Confirmed incidents from any of these four are persisted via
`artifact_store` (see `run_investigation()`), and become readable/
manageable through the Filesystem MCP server mounted at `/mcp`.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.agents.skills.loader import SkillLoader, get_skill_loader
from app.agents.state.investigation_state import InvestigationState
from app.infrastructure.filesystem.artifact_store import IncidentArtifactStore, get_artifact_store
from app.infrastructure.llm.factory import get_llm_provider
from app.infrastructure.llm.provider import LLMProvider
from app.services.investigation_service import run_investigation

router = APIRouter(tags=["investigations"])

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MiB


class InvestigationRequest(BaseModel):
    """Request body: raw application log text to investigate."""

    logs: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_UPLOAD_BYTES,
        description="Raw application log text to analyze",
    )


async def _read_uploaded_logs(file: UploadFile) -> str:
    """Validate and decode an uploaded log file into plain text.

    Shared by the upload and upload/export endpoints so the size limit,
    encoding check, and empty-file check are enforced identically by both.
    """
    raw_bytes = await file.read()

    if len(raw_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MiB limit.",
        )

    try:
        logs = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text.") from exc

    if not logs.strip():
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    return logs


def _report_as_markdown_download(report: str | None) -> Response:
    """Wrap a rendered report as a downloadable `.md` file response.

    Raises 422 if no incident was detected — there's no report to export.
    """
    if report is None:
        raise HTTPException(
            status_code=422,
            detail="No incident was detected, so there is no report to export.",
        )
    return Response(
        content=report,
        media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="incident-report.md"'},
    )


@router.post("/investigations", response_model=InvestigationState)
async def create_investigation(
    request: InvestigationRequest,
    llm: LLMProvider = Depends(get_llm_provider),
    skill_loader: SkillLoader = Depends(get_skill_loader),
    artifact_store: IncidentArtifactStore = Depends(get_artifact_store),
) -> InvestigationState:
    """Run the Monitoring -> Log Analysis -> Root Cause -> Recommendation -> Report
    pipeline over the given logs and return the final state.

    If the Monitoring Agent finds no incident, the response has
    `monitoring.incident_detected: false` and every later field is `null`.
    Otherwise the response's `incident_id` identifies the persisted
    artifacts, readable via the Filesystem MCP server.
    """
    return await run_investigation(
        logs=request.logs, llm=llm, skill_loader=skill_loader, artifact_store=artifact_store
    )


@router.post("/investigations/upload", response_model=InvestigationState)
async def create_investigation_from_file(
    file: UploadFile = File(..., description="A UTF-8 text log file to analyze"),
    llm: LLMProvider = Depends(get_llm_provider),
    skill_loader: SkillLoader = Depends(get_skill_loader),
    artifact_store: IncidentArtifactStore = Depends(get_artifact_store),
) -> InvestigationState:
    """Same pipeline as `POST /investigations`, accepting an uploaded log file
    instead of a JSON body."""
    logs = await _read_uploaded_logs(file)
    return await run_investigation(
        logs=logs, llm=llm, skill_loader=skill_loader, artifact_store=artifact_store
    )


@router.post(
    "/investigations/export",
    response_class=Response,
    responses={200: {"content": {"text/markdown": {}}}},
)
async def export_investigation_report(
    request: InvestigationRequest,
    llm: LLMProvider = Depends(get_llm_provider),
    skill_loader: SkillLoader = Depends(get_skill_loader),
    artifact_store: IncidentArtifactStore = Depends(get_artifact_store),
) -> Response:
    """Same pipeline as `POST /investigations`, returning only the final
    Markdown report as a downloadable `.md` file."""
    result = await run_investigation(
        logs=request.logs, llm=llm, skill_loader=skill_loader, artifact_store=artifact_store
    )
    return _report_as_markdown_download(result.report)


@router.post(
    "/investigations/upload/export",
    response_class=Response,
    responses={200: {"content": {"text/markdown": {}}}},
)
async def export_investigation_report_from_file(
    file: UploadFile = File(..., description="A UTF-8 text log file to analyze"),
    llm: LLMProvider = Depends(get_llm_provider),
    skill_loader: SkillLoader = Depends(get_skill_loader),
    artifact_store: IncidentArtifactStore = Depends(get_artifact_store),
) -> Response:
    """Same pipeline as `POST /investigations/upload`, returning only the
    final Markdown report as a downloadable `.md` file."""
    logs = await _read_uploaded_logs(file)
    result = await run_investigation(
        logs=logs, llm=llm, skill_loader=skill_loader, artifact_store=artifact_store
    )
    return _report_as_markdown_download(result.report)

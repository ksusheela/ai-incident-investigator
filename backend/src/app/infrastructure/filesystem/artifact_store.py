"""Filesystem-backed storage for confirmed-incident artifacts.

Deliberately a filesystem store, not a database: this exists specifically
to give the Filesystem MCP server (`infrastructure/mcp/server/`) — and,
as a side effect, the REST API — a real place to persist and retrieve
investigation artifacts. It is independent of, and much simpler than, the
domain-level persistence (`LogFile`/`Incident` entities, repositories)
still deferred to Feature 2; that future feature may supersede or
complement this one, not depend on it.

Layout, one directory per incident:

    <root>/<incident_id>/
        log.txt              raw log text submitted for this incident
        investigation.json   the full InvestigationState, incident_id included
        report.md            the rendered Markdown report (if any)
        evaluation.json       response time / confidence / quality scores (if evaluated)
"""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from app.agents.state.investigation_state import InvestigationState, Severity
from app.config import get_settings
from app.evaluation.models import EvaluationResult

LOG_FILENAME = "log.txt"
INVESTIGATION_FILENAME = "investigation.json"
REPORT_FILENAME = "report.md"
EVALUATION_FILENAME = "evaluation.json"


class IncidentNotFoundError(RuntimeError):
    """Raised when an `incident_id` doesn't correspond to a stored incident."""


class ExportedFileNotFoundError(RuntimeError):
    """Raised when a requested file doesn't exist under an incident's directory."""


@dataclass(frozen=True)
class IncidentRecord:
    """Lightweight metadata for a stored incident, for listing."""

    incident_id: str
    created_at: str
    severity: Severity
    summary: str


@dataclass(frozen=True)
class ExportedFile:
    """Metadata for one file stored under an incident's directory."""

    incident_id: str
    filename: str
    size_bytes: int


def generate_incident_id() -> str:
    """A sortable, human-readable incident id: `<UTC timestamp>-<8 hex chars>`.

    Microsecond precision (not just seconds) so two incidents saved in
    quick succession — plausible under real, automated log submission —
    still sort deterministically by `list_incidents()` instead of tying.
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def _validate_path_component(value: str, *, field_name: str) -> None:
    """Reject anything that could escape the store's root directory.

    Both `incident_id` and `filename` ultimately become path segments;
    both can arrive from an external MCP client, so both are untrusted
    input, not just user-facing API input.
    """
    if not value or "/" in value or "\\" in value or ".." in value:
        raise ValueError(f"invalid {field_name}: {value!r}")


class IncidentArtifactStore:
    """Reads and writes confirmed-incident artifacts under `root_dir`."""

    def __init__(self, root_dir: Path) -> None:
        self._root = root_dir
        self._root.mkdir(parents=True, exist_ok=True)

    def _incident_dir(self, incident_id: str) -> Path:
        _validate_path_component(incident_id, field_name="incident_id")
        return self._root / incident_id

    def save_incident(self, *, logs: str, state: InvestigationState) -> str:
        """Persist a confirmed incident's artifacts. Returns the generated incident_id.

        Only call this once Monitoring has confirmed an incident — this
        store only knows how to save, not how to decide what's worth
        saving.
        """
        incident_id = generate_incident_id()
        incident_dir = self._incident_dir(incident_id)
        incident_dir.mkdir(parents=True, exist_ok=False)

        record_state = state.model_copy(update={"incident_id": incident_id})
        (incident_dir / LOG_FILENAME).write_text(logs, encoding="utf-8")
        (incident_dir / INVESTIGATION_FILENAME).write_text(
            record_state.model_dump_json(indent=2), encoding="utf-8"
        )
        if state.report:
            (incident_dir / REPORT_FILENAME).write_text(state.report, encoding="utf-8")

        return incident_id

    def read_uploaded_log(self, incident_id: str) -> str:
        """Return the raw log text submitted for `incident_id`."""
        path = self._incident_dir(incident_id) / LOG_FILENAME
        if not path.exists():
            raise IncidentNotFoundError(incident_id)
        return path.read_text(encoding="utf-8")

    def save_report(self, incident_id: str, markdown: str) -> None:
        """Save (or overwrite) the Markdown report for an existing incident."""
        incident_dir = self._incident_dir(incident_id)
        if not incident_dir.is_dir():
            raise IncidentNotFoundError(incident_id)
        (incident_dir / REPORT_FILENAME).write_text(markdown, encoding="utf-8")

    def read_report(self, incident_id: str) -> str:
        path = self._incident_dir(incident_id) / REPORT_FILENAME
        if not path.exists():
            raise ExportedFileNotFoundError(f"{incident_id}/{REPORT_FILENAME}")
        return path.read_text(encoding="utf-8")

    def list_incidents(self, *, limit: int = 50) -> list[IncidentRecord]:
        """List stored incidents, most recently created first."""
        records = []
        for incident_dir in self._root.iterdir():
            investigation_path = incident_dir / INVESTIGATION_FILENAME
            if not incident_dir.is_dir() or not investigation_path.exists():
                continue
            data = json.loads(investigation_path.read_text(encoding="utf-8"))
            monitoring = data.get("monitoring") or {}
            records.append(
                IncidentRecord(
                    incident_id=incident_dir.name,
                    created_at=incident_dir.name.split("-", 1)[0],
                    severity=monitoring.get("severity", "none"),
                    summary=monitoring.get("summary", ""),
                )
            )
        records.sort(key=lambda record: record.created_at, reverse=True)
        return records[:limit]

    def list_exported_files(self, *, incident_id: str | None = None) -> list[ExportedFile]:
        """List files stored for one incident, or across all incidents if `incident_id` is None."""
        if incident_id is not None:
            incident_dirs = [self._incident_dir(incident_id)]
        else:
            incident_dirs = sorted(self._root.iterdir())
        files = []
        for incident_dir in incident_dirs:
            if not incident_dir.is_dir():
                continue
            for path in sorted(incident_dir.iterdir()):
                if path.is_file():
                    files.append(
                        ExportedFile(
                            incident_id=incident_dir.name,
                            filename=path.name,
                            size_bytes=path.stat().st_size,
                        )
                    )
        return files

    def delete_exported_file(self, incident_id: str, filename: str) -> None:
        """Remove a single file from an incident's directory."""
        _validate_path_component(filename, field_name="filename")
        path = self._incident_dir(incident_id) / filename
        if not path.is_file():
            raise ExportedFileNotFoundError(f"{incident_id}/{filename}")
        path.unlink()

    def save_evaluation(self, incident_id: str, evaluation: EvaluationResult) -> None:
        """Persist the evaluation (response time, confidence, quality scores) for an incident."""
        incident_dir = self._incident_dir(incident_id)
        if not incident_dir.is_dir():
            raise IncidentNotFoundError(incident_id)
        (incident_dir / EVALUATION_FILENAME).write_text(
            evaluation.model_dump_json(indent=2), encoding="utf-8"
        )

    def read_evaluation(self, incident_id: str) -> EvaluationResult:
        path = self._incident_dir(incident_id) / EVALUATION_FILENAME
        if not path.exists():
            raise ExportedFileNotFoundError(f"{incident_id}/{EVALUATION_FILENAME}")
        return EvaluationResult.model_validate_json(path.read_text(encoding="utf-8"))

    def list_evaluations(self) -> list[EvaluationResult]:
        """Every stored evaluation, most recently evaluated first.

        Incidents with no `evaluation.json` (e.g. persisted before this
        feature existed) are silently skipped rather than erroring — an
        aggregate summary should reflect what's evaluable, not fail
        outright because of one incomplete record.
        """
        evaluations = []
        for incident_dir in self._root.iterdir():
            evaluation_path = incident_dir / EVALUATION_FILENAME
            if incident_dir.is_dir() and evaluation_path.exists():
                evaluations.append(
                    EvaluationResult.model_validate_json(
                        evaluation_path.read_text(encoding="utf-8")
                    )
                )
        evaluations.sort(key=lambda evaluation: evaluation.evaluated_at, reverse=True)
        return evaluations


@lru_cache
def get_artifact_store() -> IncidentArtifactStore:
    """FastAPI dependency: the process-wide cached artifact store."""
    settings = get_settings()
    return IncidentArtifactStore(root_dir=Path(settings.incident_artifacts_dir))

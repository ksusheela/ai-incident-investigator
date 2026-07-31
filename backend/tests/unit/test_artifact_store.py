"""Unit tests for the filesystem-backed incident artifact store."""

import pytest

from app.agents.state.investigation_state import InvestigationState, MonitoringResult
from app.evaluation.models import EvaluationResult, QualityCheck, QualityScore
from app.infrastructure.filesystem.artifact_store import (
    ExportedFileNotFoundError,
    IncidentArtifactStore,
    IncidentNotFoundError,
)


def _evaluation(
    incident_id: str,
    *,
    response_time_seconds: float = 1.5,
    evaluated_at: str = "2026-07-31T00:00:00+00:00",
) -> EvaluationResult:
    passing_check = QualityCheck(name="x", passed=True, detail="d")
    return EvaluationResult(
        incident_id=incident_id,
        evaluated_at=evaluated_at,
        response_time_seconds=response_time_seconds,
        confidence_score=0.8,
        root_cause_quality=QualityScore(score=1.0, checks=[passing_check]),
        recommendation_quality=QualityScore(score=1.0, checks=[passing_check]),
    )


def _incident_state(
    *, incident_detected: bool = True, report: str | None = "# Report"
) -> InvestigationState:
    return InvestigationState(
        logs="ERROR something broke",
        monitoring=MonitoringResult(
            incident_detected=incident_detected,
            severity="medium" if incident_detected else "none",
            summary="Detected 1 error line(s); severity: medium.",
            error_count=1 if incident_detected else 0,
            warning_count=0,
            sample_errors=[],
            sample_warnings=[],
        ),
        report=report,
    )


def test_save_incident_creates_log_investigation_and_report_files(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)

    incident_id = store.save_incident(logs="ERROR something broke", state=_incident_state())

    incident_dir = tmp_path / incident_id
    assert (incident_dir / "log.txt").read_text() == "ERROR something broke"
    assert (incident_dir / "report.md").read_text() == "# Report"
    assert incident_id in (incident_dir / "investigation.json").read_text()


def test_save_incident_omits_report_file_when_no_report_produced(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)

    incident_id = store.save_incident(logs="x", state=_incident_state(report=None))

    assert not (tmp_path / incident_id / "report.md").exists()


def test_read_uploaded_log_returns_saved_content(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)
    incident_id = store.save_incident(logs="ERROR something broke", state=_incident_state())

    assert store.read_uploaded_log(incident_id) == "ERROR something broke"


def test_read_uploaded_log_raises_for_unknown_incident(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)

    with pytest.raises(IncidentNotFoundError):
        store.read_uploaded_log("does-not-exist")


def test_save_report_overwrites_existing_report(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)
    incident_id = store.save_incident(logs="x", state=_incident_state())

    store.save_report(incident_id, "# Updated report")

    assert store.read_report(incident_id) == "# Updated report"


def test_save_report_raises_for_unknown_incident(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)

    with pytest.raises(IncidentNotFoundError):
        store.save_report("does-not-exist", "# Report")


def test_read_report_raises_when_no_report_exists(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)
    incident_id = store.save_incident(logs="x", state=_incident_state(report=None))

    with pytest.raises(ExportedFileNotFoundError):
        store.read_report(incident_id)


def test_list_incidents_returns_most_recent_first(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)
    first_id = store.save_incident(logs="a", state=_incident_state())
    second_id = store.save_incident(logs="b", state=_incident_state())

    records = store.list_incidents()

    assert [r.incident_id for r in records] == sorted([first_id, second_id], reverse=True)


def test_list_incidents_respects_limit(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)
    for _ in range(3):
        store.save_incident(logs="a", state=_incident_state())

    assert len(store.list_incidents(limit=2)) == 2


def test_list_exported_files_for_one_incident(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)
    incident_id = store.save_incident(logs="a", state=_incident_state())

    files = store.list_exported_files(incident_id=incident_id)

    filenames = {f.filename for f in files}
    assert filenames == {"log.txt", "investigation.json", "report.md"}
    assert all(f.incident_id == incident_id for f in files)
    assert all(f.size_bytes > 0 for f in files)


def test_list_exported_files_across_all_incidents(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)
    store.save_incident(logs="a", state=_incident_state())
    store.save_incident(logs="b", state=_incident_state())

    files = store.list_exported_files()

    assert len({f.incident_id for f in files}) == 2


def test_list_exported_files_for_unknown_incident_is_empty(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)

    assert store.list_exported_files(incident_id="does-not-exist") == []


def test_delete_exported_file_removes_it(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)
    incident_id = store.save_incident(logs="a", state=_incident_state())

    store.delete_exported_file(incident_id, "report.md")

    assert not (tmp_path / incident_id / "report.md").exists()


def test_delete_exported_file_raises_for_missing_file(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)
    incident_id = store.save_incident(logs="a", state=_incident_state())

    with pytest.raises(ExportedFileNotFoundError):
        store.delete_exported_file(incident_id, "does-not-exist.md")


@pytest.mark.parametrize("malicious_id", ["../escape", "a/b", "a\\b", "..", ""])
def test_rejects_path_traversal_in_incident_id(tmp_path, malicious_id):
    store = IncidentArtifactStore(root_dir=tmp_path)

    with pytest.raises(ValueError):
        store.read_uploaded_log(malicious_id)


@pytest.mark.parametrize("malicious_filename", ["../../etc/passwd", "a/b", "a\\b", ".."])
def test_rejects_path_traversal_in_filename(tmp_path, malicious_filename):
    store = IncidentArtifactStore(root_dir=tmp_path)
    incident_id = store.save_incident(logs="a", state=_incident_state())

    with pytest.raises(ValueError):
        store.delete_exported_file(incident_id, malicious_filename)


def test_save_and_read_evaluation_round_trips(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)
    incident_id = store.save_incident(logs="a", state=_incident_state())

    store.save_evaluation(incident_id, _evaluation(incident_id, response_time_seconds=2.5))

    read_back = store.read_evaluation(incident_id)
    assert read_back.response_time_seconds == 2.5
    assert read_back.incident_id == incident_id


def test_save_evaluation_raises_for_unknown_incident(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)

    with pytest.raises(IncidentNotFoundError):
        store.save_evaluation("does-not-exist", _evaluation("does-not-exist"))


def test_read_evaluation_raises_when_none_saved(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)
    incident_id = store.save_incident(logs="a", state=_incident_state())

    with pytest.raises(ExportedFileNotFoundError):
        store.read_evaluation(incident_id)


def test_list_evaluations_returns_only_evaluated_incidents(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)
    evaluated_id = store.save_incident(logs="a", state=_incident_state())
    store.save_incident(logs="b", state=_incident_state())  # never evaluated
    store.save_evaluation(evaluated_id, _evaluation(evaluated_id))

    evaluations = store.list_evaluations()

    assert len(evaluations) == 1
    assert evaluations[0].incident_id == evaluated_id


def test_list_evaluations_returns_most_recent_first(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)
    older_id = store.save_incident(logs="a", state=_incident_state())
    newer_id = store.save_incident(logs="b", state=_incident_state())
    store.save_evaluation(older_id, _evaluation(older_id, evaluated_at="2026-01-01T00:00:00+00:00"))
    store.save_evaluation(newer_id, _evaluation(newer_id, evaluated_at="2026-06-01T00:00:00+00:00"))

    evaluations = store.list_evaluations()

    assert [e.incident_id for e in evaluations] == [newer_id, older_id]


def test_list_evaluations_empty_when_none_exist(tmp_path):
    store = IncidentArtifactStore(root_dir=tmp_path)
    store.save_incident(logs="a", state=_incident_state())

    assert store.list_evaluations() == []

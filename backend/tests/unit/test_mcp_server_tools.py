"""Unit tests for the Filesystem MCP server's tools, called in-process.

These exercise the real MCP protocol call path (`MCPServer.call_tool`),
not just the underlying `IncidentArtifactStore` directly (see
test_artifact_store.py for that) — confirming the MCP-facing layer itself
(argument handling, error translation) works correctly.
"""

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from app.agents.state.investigation_state import InvestigationState, MonitoringResult
from app.infrastructure.filesystem.artifact_store import (
    ExportedFileNotFoundError,
    IncidentArtifactStore,
)
from app.infrastructure.mcp.server.tools import create_mcp_server


def _incident_state(report: str = "# Report") -> InvestigationState:
    return InvestigationState(
        logs="ERROR something broke",
        monitoring=MonitoringResult(
            incident_detected=True,
            severity="medium",
            summary="Detected 1 error line(s); severity: medium.",
            error_count=1,
            warning_count=0,
            sample_errors=[],
            sample_warnings=[],
        ),
        report=report,
    )


@pytest.fixture
def store(tmp_path):
    return IncidentArtifactStore(root_dir=tmp_path)


@pytest.fixture
def server(store):
    return create_mcp_server(store)


async def test_lists_all_five_tools(server):
    tools = await server.list_tools()

    assert {t.name for t in tools} == {
        "read_uploaded_log",
        "save_report",
        "list_incidents",
        "list_exported_files",
        "delete_exported_file",
    }


async def test_read_uploaded_log_tool_returns_saved_content(server, store):
    incident_id = store.save_incident(logs="ERROR something broke", state=_incident_state())

    result = await server.call_tool("read_uploaded_log", {"incident_id": incident_id})

    assert result.content[0].text == "ERROR something broke"


async def test_read_uploaded_log_tool_raises_for_unknown_incident(server):
    with pytest.raises(ToolError):
        await server.call_tool("read_uploaded_log", {"incident_id": "does-not-exist"})


async def test_save_report_tool_overwrites_report(server, store):
    incident_id = store.save_incident(logs="x", state=_incident_state())

    await server.call_tool("save_report", {"incident_id": incident_id, "markdown": "# New"})

    assert store.read_report(incident_id) == "# New"


async def test_save_report_tool_raises_for_unknown_incident(server):
    with pytest.raises(ToolError):
        await server.call_tool("save_report", {"incident_id": "nope", "markdown": "# x"})


async def test_list_incidents_tool_returns_stored_incidents(server, store):
    incident_id = store.save_incident(logs="x", state=_incident_state())

    result = await server.call_tool("list_incidents", {})

    # For list-returning tools, `content` holds one TextContent block per
    # list element; `structured_content["result"]` holds the full
    # structured Python list — use that rather than parsing `content`.
    records = result.structured_content["result"]
    assert any(record["incident_id"] == incident_id for record in records)
    assert any(record["severity"] == "medium" for record in records)


async def test_list_exported_files_tool_filters_by_incident(server, store):
    incident_id = store.save_incident(logs="x", state=_incident_state())
    store.save_incident(logs="y", state=_incident_state())

    result = await server.call_tool("list_exported_files", {"incident_id": incident_id})

    files = result.structured_content["result"]
    assert {f["incident_id"] for f in files} == {incident_id}
    assert {f["filename"] for f in files} == {"log.txt", "investigation.json", "report.md"}


async def test_delete_exported_file_tool_removes_file(server, store):
    incident_id = store.save_incident(logs="x", state=_incident_state())

    await server.call_tool(
        "delete_exported_file", {"incident_id": incident_id, "filename": "report.md"}
    )

    with pytest.raises(ExportedFileNotFoundError):
        store.read_report(incident_id)


async def test_delete_exported_file_tool_raises_for_missing_file(server, store):
    incident_id = store.save_incident(logs="x", state=_incident_state())

    with pytest.raises(ToolError):
        await server.call_tool(
            "delete_exported_file", {"incident_id": incident_id, "filename": "nope.md"}
        )


async def test_tools_reject_path_traversal_attempts(server):
    with pytest.raises(ToolError):
        await server.call_tool("read_uploaded_log", {"incident_id": "../../etc/passwd"})

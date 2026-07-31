"""End-to-end test: a confirmed incident run through the real REST API is
persisted to the filesystem and readable back out through the Filesystem
MCP server's tools — the full round trip this feature exists for.
"""

import json

from fastapi import FastAPI
from httpx import AsyncClient
from starlette.routing import Mount

from app.infrastructure.filesystem.artifact_store import get_artifact_store
from app.infrastructure.llm.factory import get_llm_provider
from app.infrastructure.mcp.server.tools import create_mcp_server
from tests.fakes import FakeLLMProvider

_ROOT_CAUSE_RESPONSE = json.dumps(
    {
        "hypothesis": "payments-db connection pool exhaustion",
        "matched_pattern": "connection_pool_exhaustion",
        "confidence_score": 0.85,
        "reasoning": "Repeated timeouts under load match this pattern.",
        "contributing_factors": ["undersized connection pool"],
    }
)
_RECOMMENDATION_RESPONSE = json.dumps(
    {
        "code_fixes": [],
        "configuration_changes": [
            {"description": "Increase pool size", "rationale": "Pool is undersized."}
        ],
        "database_improvements": [],
    }
)
_REPORT_RESPONSE = json.dumps(
    {
        "summary": "Checkout failed due to payments-db timeouts.",
        "next_steps": ["Notify the payments team"],
    }
)
_INCIDENT_LOGS = "ERROR checkout-service: 500\nERROR checkout-service: db timeout"


def test_mcp_server_is_mounted_at_slash_mcp(app: FastAPI) -> None:
    mounts = [route for route in app.routes if isinstance(route, Mount)]
    assert any(route.path == "/mcp" for route in mounts)


async def test_confirmed_incident_is_readable_through_mcp_tools(
    app: FastAPI, client: AsyncClient
) -> None:
    fake_llm = FakeLLMProvider(
        responses=[_ROOT_CAUSE_RESPONSE, _RECOMMENDATION_RESPONSE, _REPORT_RESPONSE]
    )
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm

    response = await client.post("/api/v1/investigations", json={"logs": _INCIDENT_LOGS})
    assert response.status_code == 200
    incident_id = response.json()["incident_id"]
    assert incident_id is not None

    # The MCP server is built over the same cached artifact store the API
    # just wrote to — read the incident back purely through MCP tools,
    # never touching the store directly, to prove the whole path works.
    mcp_server = create_mcp_server(get_artifact_store())

    log_result = await mcp_server.call_tool("read_uploaded_log", {"incident_id": incident_id})
    assert log_result.content[0].text == _INCIDENT_LOGS

    incidents_result = await mcp_server.call_tool("list_incidents", {})
    incidents = incidents_result.structured_content["result"]
    assert any(record["incident_id"] == incident_id for record in incidents)

    files_result = await mcp_server.call_tool(
        "list_exported_files", {"incident_id": incident_id}
    )
    filenames = {f["filename"] for f in files_result.structured_content["result"]}
    assert filenames == {"log.txt", "investigation.json", "report.md", "evaluation.json"}

    await mcp_server.call_tool(
        "save_report", {"incident_id": incident_id, "markdown": "# Edited report"}
    )
    reread_log_result = await mcp_server.call_tool(
        "read_uploaded_log", {"incident_id": incident_id}
    )
    assert reread_log_result.content[0].text == _INCIDENT_LOGS  # unaffected by the report edit


async def test_clean_logs_never_appear_in_mcp_incident_listing(
    app: FastAPI, client: AsyncClient
) -> None:
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider(responses=[])

    response = await client.post("/api/v1/investigations", json={"logs": "INFO: all good"})
    assert response.status_code == 200
    assert response.json()["incident_id"] is None

    mcp_server = create_mcp_server(get_artifact_store())
    incidents_result = await mcp_server.call_tool("list_incidents", {})

    assert incidents_result.structured_content["result"] == []

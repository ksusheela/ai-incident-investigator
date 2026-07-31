"""Integration tests for the investigation endpoints, through the real API layer."""

import json

from fastapi import FastAPI
from httpx import AsyncClient

from app.infrastructure.llm.factory import get_llm_provider
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


async def test_investigation_endpoint_returns_no_incident(
    app: FastAPI, client: AsyncClient
) -> None:
    # No LLM-backed agent should run when Monitoring finds nothing, so an
    # empty response queue also proves that.
    fake_llm = FakeLLMProvider(responses=[])
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm

    response = await client.post("/api/v1/investigations", json={"logs": "INFO: ok"})

    assert response.status_code == 200
    body = response.json()
    assert body["monitoring"]["incident_detected"] is False
    assert body["monitoring"]["severity"] == "none"
    assert body["report"] is None


async def test_investigation_endpoint_rejects_empty_logs(app: FastAPI, client: AsyncClient) -> None:
    # A working LLM dependency is still provided here so this test isolates
    # request validation from the separate "LLM not configured" failure mode.
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider(responses=[])

    response = await client.post("/api/v1/investigations", json={"logs": ""})

    assert response.status_code == 422


async def test_upload_endpoint_runs_investigation_over_file_contents(
    app: FastAPI, client: AsyncClient
) -> None:
    fake_llm = FakeLLMProvider(responses=[])
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm

    file_content = b"2026-07-31T10:00:00Z INFO checkout-service: request handled in 12ms"
    response = await client.post(
        "/api/v1/investigations/upload",
        files={"file": ("app.log", file_content, "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["monitoring"]["incident_detected"] is False


async def test_upload_endpoint_rejects_empty_file(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider(responses=[])

    response = await client.post(
        "/api/v1/investigations/upload",
        files={"file": ("empty.log", b"   ", "text/plain")},
    )

    assert response.status_code == 422


async def test_upload_endpoint_rejects_non_utf8_file(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider(responses=[])

    response = await client.post(
        "/api/v1/investigations/upload",
        files={"file": ("binary.log", b"\xff\xfe\x00\x01", "text/plain")},
    )

    assert response.status_code == 400


async def test_investigation_succeeds_without_llm_configured_when_no_incident(
    app: FastAPI, client: AsyncClient
) -> None:
    """No `dependency_overrides` here — this exercises the *real*
    `get_llm_provider` dependency with no ANTHROPIC_API_KEY set (the actual
    state of the test environment). Logs with no incident must still
    succeed, proving the LLM provider is constructed lazily rather than
    eagerly at dependency-resolution time.
    """
    response = await client.post("/api/v1/investigations", json={"logs": "INFO: all good"})

    assert response.status_code == 200
    assert response.json()["monitoring"]["incident_detected"] is False


async def test_investigation_fails_clearly_when_llm_needed_but_not_configured(
    app: FastAPI, client: AsyncClient
) -> None:
    """Same real dependency, but logs that *do* need the LLM — should fail
    with a clear 503 once Log Analysis actually tries to use it, not a
    stack trace."""
    response = await client.post(
        "/api/v1/investigations", json={"logs": "ERROR: 500 checkout-service"}
    )

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


async def test_export_endpoint_returns_downloadable_markdown_report(
    app: FastAPI, client: AsyncClient
) -> None:
    fake_llm = FakeLLMProvider(
        responses=[_ROOT_CAUSE_RESPONSE, _RECOMMENDATION_RESPONSE, _REPORT_RESPONSE]
    )
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm

    response = await client.post(
        "/api/v1/investigations/export",
        json={"logs": "ERROR checkout-service: 500\nERROR checkout-service: db timeout"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert 'attachment; filename="incident-report.md"' in response.headers["content-disposition"]
    assert response.text.startswith("# Incident Report")
    assert "## Next Steps" in response.text


async def test_export_endpoint_rejects_when_no_incident_detected(
    app: FastAPI, client: AsyncClient
) -> None:
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider(responses=[])

    response = await client.post("/api/v1/investigations/export", json={"logs": "INFO: all good"})

    assert response.status_code == 422


async def test_upload_export_endpoint_returns_downloadable_markdown_report(
    app: FastAPI, client: AsyncClient
) -> None:
    fake_llm = FakeLLMProvider(
        responses=[_ROOT_CAUSE_RESPONSE, _RECOMMENDATION_RESPONSE, _REPORT_RESPONSE]
    )
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm

    file_content = b"ERROR checkout-service: 500\nERROR checkout-service: db timeout"
    response = await client.post(
        "/api/v1/investigations/upload/export",
        files={"file": ("app.log", file_content, "text/plain")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.text.startswith("# Incident Report")

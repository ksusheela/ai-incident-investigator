"""Integration tests for the incidents listing endpoints."""

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
        "reasoning": "Repeated timeout errors correlated with an error burst indicate exhaustion.",
        "contributing_factors": ["undersized connection pool"],
    }
)
_RECOMMENDATION_RESPONSE = json.dumps(
    {
        "code_fixes": [],
        "configuration_changes": [
            {
                "description": "Increase pool size",
                "rationale": "The pool is undersized for current peak traffic levels.",
            }
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


async def test_list_incidents_is_empty_with_nothing_confirmed(
    app: FastAPI, client: AsyncClient
) -> None:
    response = await client.get("/api/v1/incidents")

    assert response.status_code == 200
    assert response.json() == []


async def test_list_incidents_reflects_a_confirmed_incident(
    app: FastAPI, client: AsyncClient
) -> None:
    fake_llm = FakeLLMProvider(
        responses=[_ROOT_CAUSE_RESPONSE, _RECOMMENDATION_RESPONSE, _REPORT_RESPONSE]
    )
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm

    investigation_response = await client.post(
        "/api/v1/investigations",
        json={"logs": "ERROR checkout-service: 500\nERROR checkout-service: db timeout"},
    )
    assert investigation_response.status_code == 200
    incident_id = investigation_response.json()["incident_id"]

    list_response = await client.get("/api/v1/incidents")

    assert list_response.status_code == 200
    body = list_response.json()
    assert len(body) == 1
    assert body[0]["incident_id"] == incident_id
    assert body[0]["severity"] != "none"


async def test_get_incident_report_returns_markdown(app: FastAPI, client: AsyncClient) -> None:
    fake_llm = FakeLLMProvider(
        responses=[_ROOT_CAUSE_RESPONSE, _RECOMMENDATION_RESPONSE, _REPORT_RESPONSE]
    )
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm

    investigation_response = await client.post(
        "/api/v1/investigations",
        json={"logs": "ERROR checkout-service: 500\nERROR checkout-service: db timeout"},
    )
    incident_id = investigation_response.json()["incident_id"]

    report_response = await client.get(f"/api/v1/incidents/{incident_id}/report")

    assert report_response.status_code == 200
    assert report_response.headers["content-type"].startswith("text/markdown")
    assert "Checkout failed" in report_response.text


async def test_get_incident_report_404s_for_unknown_incident(
    app: FastAPI, client: AsyncClient
) -> None:
    response = await client.get("/api/v1/incidents/does-not-exist/report")

    assert response.status_code == 404

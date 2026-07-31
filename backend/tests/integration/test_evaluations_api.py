"""Integration tests for GET /api/v1/evaluations/summary."""

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


async def test_evaluation_summary_is_empty_with_no_incidents(
    app: FastAPI, client: AsyncClient
) -> None:
    response = await client.get("/api/v1/evaluations/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["evaluated_count"] == 0
    assert body["avg_response_time_seconds"] is None


async def test_evaluation_summary_reflects_confirmed_incidents(
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

    summary_response = await client.get("/api/v1/evaluations/summary")

    assert summary_response.status_code == 200
    body = summary_response.json()
    assert body["evaluated_count"] == 1
    assert body["avg_confidence_score"] == 0.85
    assert body["avg_response_time_seconds"] > 0
    assert 0.0 <= body["avg_root_cause_quality"] <= 1.0
    assert 0.0 <= body["avg_recommendation_quality"] <= 1.0


async def test_evaluation_summary_excludes_clean_investigations(
    app: FastAPI, client: AsyncClient
) -> None:
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider(responses=[])

    response = await client.post("/api/v1/investigations", json={"logs": "INFO: all good"})
    assert response.status_code == 200

    summary_response = await client.get("/api/v1/evaluations/summary")

    assert summary_response.json()["evaluated_count"] == 0


async def test_list_evaluations_is_empty_with_nothing_evaluated(
    app: FastAPI, client: AsyncClient
) -> None:
    response = await client.get("/api/v1/evaluations")

    assert response.status_code == 200
    assert response.json() == []


async def test_list_evaluations_reflects_a_confirmed_incident(
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
    incident_id = investigation_response.json()["incident_id"]

    list_response = await client.get("/api/v1/evaluations")

    assert list_response.status_code == 200
    body = list_response.json()
    assert len(body) == 1
    assert body[0]["incident_id"] == incident_id


async def test_get_evaluation_returns_one_incidents_evaluation(
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
    incident_id = investigation_response.json()["incident_id"]

    evaluation_response = await client.get(f"/api/v1/evaluations/{incident_id}")

    assert evaluation_response.status_code == 200
    assert evaluation_response.json()["confidence_score"] == 0.85


async def test_get_evaluation_404s_for_unknown_incident(app: FastAPI, client: AsyncClient) -> None:
    response = await client.get("/api/v1/evaluations/does-not-exist")

    assert response.status_code == 404

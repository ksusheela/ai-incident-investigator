"""Tests for the /api/v1/health endpoint."""

from httpx import AsyncClient


async def test_health_returns_ok_and_confirms_db_connection(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db_connected"] is True
    assert body["app_env"] == "test"

"""Integration test guarding against a regression to the CORS bug where the
frontend's `fetch()` calls were silently blocked by the browser even though
server-to-server requests (curl, this very test's ASGITransport) succeeded.
"""

from fastapi import FastAPI
from httpx import AsyncClient


async def test_allowed_origin_gets_cors_header(app: FastAPI, client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/health", headers={"Origin": "http://localhost:5173"}
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_disallowed_origin_gets_no_cors_header(app: FastAPI, client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/health", headers={"Origin": "http://evil.example.com"}
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


async def test_preflight_request_is_handled(app: FastAPI, client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/investigations",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

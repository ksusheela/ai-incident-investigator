"""Shared pytest fixtures for the backend test suite."""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def temp_database_url(tmp_path: Path) -> str:
    """Point the app at a throwaway SQLite file for test isolation."""
    db_file = tmp_path / "test_incident_investigator.db"
    return f"sqlite+aiosqlite:///{db_file.as_posix()}"


@pytest.fixture
def app(temp_database_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """A fresh FastAPI app bound to a temp SQLite DB and a temp artifact store.

    Exposed separately from `client` so tests can set
    `app.dependency_overrides` (e.g. swapping in a fake LLM provider)
    before issuing requests.
    """
    monkeypatch.setenv("DATABASE_URL", temp_database_url)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("INCIDENT_ARTIFACTS_DIR", str(tmp_path / "incidents"))

    # Settings/engine/store are cached module-level singletons; clear them
    # so this test's env vars take effect instead of a previously imported
    # config (and so tests never write into the real backend/data/ tree).
    from app import config, database
    from app.infrastructure.filesystem import artifact_store

    config.get_settings.cache_clear()
    database._engine = database.create_engine(config.get_settings())
    database._session_factory = database.async_sessionmaker(
        bind=database._engine, expire_on_commit=False
    )
    artifact_store.get_artifact_store.cache_clear()

    from app.main import create_app

    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """An httpx AsyncClient bound to the `app` fixture."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client

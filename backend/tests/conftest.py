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
def app(temp_database_url: str, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """A fresh FastAPI app bound to a temp SQLite DB.

    Exposed separately from `client` so tests can set
    `app.dependency_overrides` (e.g. swapping in a fake LLM provider)
    before issuing requests.
    """
    monkeypatch.setenv("DATABASE_URL", temp_database_url)
    monkeypatch.setenv("APP_ENV", "test")

    # Settings/engine are cached module-level singletons; clear them so this
    # test's env vars take effect instead of a previously imported config.
    from app import config, database

    config.get_settings.cache_clear()
    database._engine = database.create_engine(config.get_settings())
    database._session_factory = database.async_sessionmaker(
        bind=database._engine, expire_on_commit=False
    )

    from app.main import create_app

    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """An httpx AsyncClient bound to the `app` fixture."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client

"""Shared pytest fixtures for the backend test suite."""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def temp_database_url(tmp_path: Path) -> str:
    """Point the app at a throwaway SQLite file for test isolation."""
    db_file = tmp_path / "test_incident_investigator.db"
    return f"sqlite+aiosqlite:///{db_file.as_posix()}"


@pytest.fixture
async def client(
    temp_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient, None]:
    """An httpx AsyncClient bound to the FastAPI app, using a temp SQLite DB."""
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

    app = create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client

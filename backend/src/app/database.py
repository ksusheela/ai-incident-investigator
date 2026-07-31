"""Async SQLAlchemy engine, session factory, and FastAPI dependency."""

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings, get_settings


def _ensure_sqlite_directory_exists(database_url: str) -> None:
    """Create the parent directory for a file-based SQLite URL if needed.

    aiosqlite fails to open a database file whose parent directory does not
    exist yet; in-memory URLs (`:memory:`) have no filesystem path and are
    skipped.
    """
    if "sqlite" not in database_url or ":memory:" in database_url:
        return

    db_path = database_url.split("///")[-1]
    parent = Path(db_path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)


def create_engine(settings: Settings) -> AsyncEngine:
    """Build the async SQLAlchemy engine for the configured database URL."""
    _ensure_sqlite_directory_exists(settings.database_url)
    return create_async_engine(settings.database_url, echo=False, future=True)


_engine: AsyncEngine = create_engine(get_settings())
_session_factory = async_sessionmaker(bind=_engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped async DB session."""
    async with _session_factory() as session:
        yield session


async def check_database_connection(session: AsyncSession) -> bool:
    """Execute a trivial query to verify the database is reachable."""
    result = await session.execute(text("SELECT 1"))
    return result.scalar_one() == 1

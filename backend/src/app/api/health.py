"""Health check endpoint."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import check_database_connection, get_db_session

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Response body for the health check endpoint."""

    status: str
    app_name: str
    app_version: str
    app_env: str
    db_connected: bool


@router.get("/health", response_model=HealthResponse)
async def get_health(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Report application liveness and database connectivity."""
    db_connected = await check_database_connection(session)
    return HealthResponse(
        status="ok" if db_connected else "degraded",
        app_name=settings.app_name,
        app_version=settings.app_version,
        app_env=settings.app_env,
        db_connected=db_connected,
    )

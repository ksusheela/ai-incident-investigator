"""FastAPI application factory."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.agents.errors import AgentOutputError
from app.api.health import router as health_router
from app.api.investigations import router as investigations_router
from app.config import Settings, get_settings
from app.infrastructure.llm.factory import LLMConfigurationError
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)

API_DESCRIPTION = """
Backend API for **AI Incident Investigator** — upload application logs, detect
production incidents, run automated root-cause analysis, get fix suggestions,
and generate incident reports via a multi-agent AI pipeline.
""".strip()

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Liveness/readiness checks, including live database connectivity.",
    },
    {
        "name": "investigations",
        "description": "Runs the LangGraph multi-agent pipeline over application logs.",
    },
]


def _build_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        logger.info("%s starting up in '%s' environment", settings.app_name, settings.app_env)
        yield
        logger.info("%s shutting down", settings.app_name)

    return lifespan


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(settings)

    # Interactive API docs are a diagnostic/dev surface, not something to
    # expose publicly once the app is actually in production.
    docs_enabled = settings.app_env != "production"

    app = FastAPI(
        title=settings.app_name,
        description=API_DESCRIPTION,
        version=settings.app_version,
        openapi_tags=OPENAPI_TAGS,
        license_info={
            "name": "Apache 2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0",
        },
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=_build_lifespan(settings),
    )

    app.include_router(health_router, prefix=settings.api_v1_prefix)
    app.include_router(investigations_router, prefix=settings.api_v1_prefix)

    @app.exception_handler(LLMConfigurationError)
    async def handle_llm_configuration_error(
        _: Request, exc: LLMConfigurationError
    ) -> JSONResponse:
        logger.error("LLM configuration error: %s", exc)
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(AgentOutputError)
    async def handle_agent_output_error(_: Request, exc: AgentOutputError) -> JSONResponse:
        logger.error("Agent output error: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"detail": f"{exc.agent_name} returned an unexpected response from the LLM."},
        )

    return app


app = create_app()

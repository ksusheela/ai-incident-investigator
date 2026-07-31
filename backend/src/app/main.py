"""FastAPI application factory."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server import MCPServer

from app.agents.errors import AgentOutputError
from app.api.evaluations import router as evaluations_router
from app.api.health import router as health_router
from app.api.incidents import router as incidents_router
from app.api.investigations import router as investigations_router
from app.config import Settings, get_settings
from app.infrastructure.filesystem.artifact_store import get_artifact_store
from app.infrastructure.llm.factory import LLMConfigurationError
from app.infrastructure.mcp.server.tools import create_mcp_server
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
    {
        "name": "evaluation",
        "description": "Aggregate response-time/confidence/quality metrics for the dashboard.",
    },
    {
        "name": "incidents",
        "description": "Read-only listing of confirmed incidents and their reports.",
    },
]

MCP_MOUNT_PATH = "/mcp"


def _build_lifespan(settings: Settings, mcp_server: MCPServer):
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        logger.info("%s starting up in '%s' environment", settings.app_name, settings.app_env)
        # The Streamable HTTP transport's session manager must be running
        # for the mounted MCP app to actually serve requests — it's not
        # started automatically just by mounting the ASGI app.
        async with mcp_server.session_manager.run():
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

    mcp_server = create_mcp_server(get_artifact_store())
    # streamable_http_path="/" so the app handles requests at exactly the
    # path FastAPI mounts it under (MCP_MOUNT_PATH) rather than that path
    # plus MCP's own default "/mcp" suffix.
    mcp_asgi_app = mcp_server.streamable_http_app(streamable_http_path="/")

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
        lifespan=_build_lifespan(settings, mcp_server),
    )

    # Without this, every frontend `fetch()` call is silently blocked by
    # the browser's CORS policy -- a server-to-server curl (or the test
    # suite's ASGITransport, which never goes through a browser) would
    # still succeed, masking the failure. Origins come from Settings so
    # dev/Docker/prod can each allow only their own frontend origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix=settings.api_v1_prefix)
    app.include_router(investigations_router, prefix=settings.api_v1_prefix)
    app.include_router(evaluations_router, prefix=settings.api_v1_prefix)
    app.include_router(incidents_router, prefix=settings.api_v1_prefix)
    app.mount(MCP_MOUNT_PATH, mcp_asgi_app)

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

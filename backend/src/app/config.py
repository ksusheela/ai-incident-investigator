"""Application configuration sourced from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the AI Incident Investigator backend.

    All values can be overridden via environment variables or a `.env`
    file in the `backend/` directory (see `.env.example`).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Incident Investigator"
    app_version: str = "0.1.0"
    app_env: str = "local"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./data/incident_investigator.db"

    # LLM provider used by the agent pipeline. "anthropic" or "gemini".
    llm_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    # Filesystem root where confirmed-incident artifacts (uploaded log,
    # full investigation JSON, generated report) are persisted, and which
    # the Filesystem MCP server exposes as tools.
    incident_artifacts_dir: str = "./data/incidents"

    # Comma-separated browser origins allowed to call the API cross-origin
    # (the frontend dev server and, in Docker, the browser-facing nginx
    # port -- both default to http://localhost:5173, see docker-compose*.yml).
    # Without this, the frontend's `fetch()` calls are blocked by the
    # browser's same-origin policy even though a server-to-server curl
    # would succeed -- CORS is enforced by the browser, not the server.
    cors_allowed_origins: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        """`cors_allowed_origins` split into a list, blanks removed."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance.

    Cached so the environment/`.env` file is only parsed once per process,
    while remaining overridable in tests via `get_settings.cache_clear()`.
    """
    return Settings()

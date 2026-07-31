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


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance.

    Cached so the environment/`.env` file is only parsed once per process,
    while remaining overridable in tests via `get_settings.cache_clear()`.
    """
    return Settings()

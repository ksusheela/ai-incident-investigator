"""Selects and caches the configured LLMProvider implementation."""

from functools import lru_cache

from app.config import Settings, get_settings
from app.infrastructure.llm.anthropic_provider import AnthropicProvider
from app.infrastructure.llm.gemini_provider import GeminiProvider
from app.infrastructure.llm.provider import LLMProvider


class LLMConfigurationError(RuntimeError):
    """Raised when the configured LLM provider is missing required setup."""


def build_llm_provider(settings: Settings) -> LLMProvider:
    """Construct the LLMProvider named by `settings.llm_provider`.

    Fails fast with a clear error rather than constructing a client that
    would only fail later, deep inside an agent call, if a key is missing.
    """
    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMConfigurationError(
                "LLM_PROVIDER is 'anthropic' but ANTHROPIC_API_KEY is not set."
            )
        return AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.anthropic_model)

    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            raise LLMConfigurationError("LLM_PROVIDER is 'gemini' but GEMINI_API_KEY is not set.")
        return GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)

    raise LLMConfigurationError(
        f"Unknown LLM_PROVIDER '{settings.llm_provider}' (expected 'anthropic' or 'gemini')."
    )


class _LazyLLMProvider:
    """Defers constructing the real provider until the first `complete()` call.

    FastAPI resolves `Depends(get_llm_provider)` for every request to this
    endpoint, regardless of whether the request ends up needing an LLM at
    all — e.g. the Monitoring Agent's short-circuit means most of the
    pipeline (and thus every LLM call) is skipped for logs with no
    incident. Without this wrapper, requests that would otherwise complete
    fine without any LLM would still fail with `LLMConfigurationError` just
    because a key isn't configured — the error would come from dependency
    resolution, not from the request actually needing the LLM.
    """

    def __init__(self) -> None:
        self._delegate: LLMProvider | None = None

    async def complete(self, *, system: str, prompt: str) -> str:
        if self._delegate is None:
            self._delegate = build_llm_provider(get_settings())
        return await self._delegate.complete(system=system, prompt=prompt)


@lru_cache
def get_llm_provider() -> LLMProvider:
    """FastAPI dependency: a process-wide cached, lazily-constructed LLMProvider."""
    return _LazyLLMProvider()

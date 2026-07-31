"""LLM provider port — the interface every concrete provider adapter implements."""

from typing import Protocol


class LLMProvider(Protocol):
    """A minimal, provider-agnostic text-completion interface.

    Agents depend on this Protocol, never on a concrete SDK client, so the
    underlying model (Claude, Gemini, or a test fake) can be swapped without
    touching agent code.
    """

    async def complete(self, *, system: str, prompt: str) -> str:
        """Return the model's raw text response to `prompt` under `system`."""
        ...

"""Claude (Anthropic) implementation of the LLMProvider port."""

from anthropic import AsyncAnthropic

_MAX_TOKENS = 2048


class AnthropicProvider:
    """Calls Claude via the official async Anthropic client."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(self, *, system: str, prompt: str) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

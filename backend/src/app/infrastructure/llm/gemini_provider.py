"""Gemini implementation of the LLMProvider port."""

from google import genai
from google.genai import types


class GeminiProvider:
    """Calls Gemini via the official async `google-genai` client."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def complete(self, *, system: str, prompt: str) -> str:
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        return response.text

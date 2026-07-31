"""Test doubles shared across the backend test suite."""


class FakeLLMProvider:
    """An LLMProvider that returns canned responses in call order.

    Each call to `complete()` pops the next response off the queue and
    records the (system, prompt) it was called with, so tests can assert
    on both what the agent produced and what it asked for.
    """

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    async def complete(self, *, system: str, prompt: str) -> str:
        self.calls.append((system, prompt))
        return self._responses.pop(0)

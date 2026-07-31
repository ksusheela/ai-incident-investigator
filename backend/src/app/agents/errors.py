"""Exceptions shared across agent nodes."""


class AgentOutputError(RuntimeError):
    """Raised when an agent's LLM response doesn't match its expected schema."""

    def __init__(self, agent_name: str, raw_output: str, cause: Exception) -> None:
        super().__init__(f"{agent_name} returned unparseable output: {raw_output!r}")
        self.agent_name = agent_name
        self.raw_output = raw_output
        self.__cause__ = cause

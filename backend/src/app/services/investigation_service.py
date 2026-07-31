"""Application/use-case layer for running an incident investigation."""

from app.agents.graphs.investigation_graph import build_investigation_graph
from app.agents.state.investigation_state import InvestigationState
from app.infrastructure.llm.provider import LLMProvider


async def run_investigation(*, logs: str, llm: LLMProvider) -> InvestigationState:
    """Run the full investigation pipeline over `logs` and return the final state."""
    graph = build_investigation_graph(llm)
    result = await graph.ainvoke(InvestigationState(logs=logs))
    return InvestigationState.model_validate(result)

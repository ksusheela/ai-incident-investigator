"""LangGraph orchestrator wiring the five investigation agents together.

Flow:

    Monitoring Agent
          |
   (incident detected?) --- no ---> END
          | yes
    Log Analysis Agent
          |
    Root Cause Agent
          |
    Recommendation Agent
          |
    Report Agent
          |
         END

Monitoring and Log Analysis run first — deterministically, with no LLM
call, see `monitoring_agent.py` and `log_analysis_agent.py` — and the
conditional edge after Monitoring short-circuits the pipeline when it
finds nothing worth investigating: the three remaining agents (each an
LLM call) never run for logs that don't warrant it.
"""

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.nodes.log_analysis_agent import log_analysis_agent
from app.agents.nodes.monitoring_agent import monitoring_agent
from app.agents.nodes.recommendation_agent import make_recommendation_agent
from app.agents.nodes.report_agent import make_report_agent
from app.agents.nodes.root_cause_agent import make_root_cause_agent
from app.agents.skills.loader import SkillLoader
from app.agents.state.investigation_state import InvestigationState
from app.infrastructure.llm.provider import LLMProvider

MONITORING = "monitoring"
LOG_ANALYSIS = "log_analysis"
ROOT_CAUSE = "root_cause"
RECOMMENDATION = "recommendation"
REPORT = "report"


def _route_after_monitoring(state: InvestigationState) -> str:
    return LOG_ANALYSIS if state.monitoring and state.monitoring.incident_detected else END


def build_investigation_graph(llm: LLMProvider, skill_loader: SkillLoader) -> CompiledStateGraph:
    """Build and compile the incident-investigation graph for `llm`.

    A fresh graph is built per provider rather than shared globally, since
    each LLM-backed node closes over `llm` — see the `make_*_agent`
    factories. Monitoring and Log Analysis have no such dependency and are
    wired in directly. `skill_loader` is threaded to Root Cause, the one
    agent augmented with Agent Skills — see `root_cause_agent.py`.
    """
    graph = StateGraph(InvestigationState)

    graph.add_node(MONITORING, monitoring_agent)
    graph.add_node(LOG_ANALYSIS, log_analysis_agent)
    graph.add_node(ROOT_CAUSE, make_root_cause_agent(llm, skill_loader))
    graph.add_node(RECOMMENDATION, make_recommendation_agent(llm))
    graph.add_node(REPORT, make_report_agent(llm))

    graph.set_entry_point(MONITORING)
    graph.add_conditional_edges(
        MONITORING,
        _route_after_monitoring,
        {LOG_ANALYSIS: LOG_ANALYSIS, END: END},
    )
    graph.add_edge(LOG_ANALYSIS, ROOT_CAUSE)
    graph.add_edge(ROOT_CAUSE, RECOMMENDATION)
    graph.add_edge(RECOMMENDATION, REPORT)
    graph.add_edge(REPORT, END)

    return graph.compile()

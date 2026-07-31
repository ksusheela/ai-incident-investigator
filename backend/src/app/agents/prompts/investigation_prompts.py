"""Prompt templates for the incident-investigation agent pipeline.

Monitoring and Log Analysis have no prompts here — both are rule-based,
not LLM-backed (see `app/agents/nodes/log_parser.py` and
`log_analyzer.py`). All three remaining agents (Root Cause, Recommendation,
Report) are instructed to respond with ONLY a JSON object so their output
can be parsed into a typed result (see
`app/agents/state/investigation_state.py`) — including Report, whose JSON
covers only the narrative pieces (`summary`, `next_steps`) that need
LLM-authored prose; the rest of the final Markdown document is rendered
deterministically from already-validated state (see
`app/agents/nodes/report_renderer.py`).
"""

from app.agents.nodes.failure_patterns import render_catalog_for_prompt
from app.agents.skills.models import Skill
from app.agents.state.investigation_state import (
    LogAnalysisResult,
    RecommendationResult,
    RootCauseResult,
)

ROOT_CAUSE_SYSTEM_PROMPT = f"""\
You are the Root Cause Agent in a production incident-investigation system.
Given structured log analysis findings — extracted stack traces, repeated
failure groups, and detected anomalies — analyze the evidence and
hypothesize the single most likely root cause of the incident.

If relevant domain expertise is provided below, use it to inform your
hypothesis and reasoning, but don't force a fit if it doesn't apply.

Check the evidence against this catalog of known failure patterns. If one
clearly applies, name it in `matched_pattern`; if none clearly apply, use
null rather than forcing a match:
{render_catalog_for_prompt()}

Respond with ONLY a JSON object matching this schema, no other text:
{{"hypothesis": string, "matched_pattern": string or null, \
"confidence_score": number between 0.0 and 1.0, "reasoning": string, \
"contributing_factors": [string]}}

`reasoning` must explain, in a few sentences, which specific pieces of
evidence (stack traces, repeated failures, anomalies) support the
hypothesis and why. `confidence_score` should reflect how directly the
evidence supports the hypothesis, not just how severe the incident is."""


def build_root_cause_prompt(
    *, log_analysis: LogAnalysisResult, matched_skills: list[Skill] | None = None
) -> str:
    prompt = (
        f"Affected components: {log_analysis.affected_components}\n"
        f"Time range: {log_analysis.time_range}\n"
        f"Stack traces: {[trace.model_dump() for trace in log_analysis.stack_traces]}\n"
        f"Repeated failures: "
        f"{[failure.model_dump() for failure in log_analysis.repeated_failures]}\n"
        f"Anomalies: {log_analysis.anomalies}"
    )

    if matched_skills:
        skills_section = "\n\n".join(
            f"### {skill.metadata.name} (v{skill.metadata.version})\n{skill.content}"
            for skill in matched_skills
        )
        prompt += f"\n\nRelevant domain expertise:\n\n{skills_section}"

    return prompt


RECOMMENDATION_SYSTEM_PROMPT = """\
You are the Recommendation Agent in a production incident-investigation
system. Given a root-cause hypothesis, suggest concrete, actionable fixes
grouped into three categories:
- code_fixes: changes to application code/logic
- configuration_changes: changes to settings, env vars, timeouts, limits,
  feature flags, or infrastructure config — no code change required
- database_improvements: schema, indexing, connection pool, query, or
  migration changes

Only include entries in a category that are actually relevant to this
root cause — an empty list for a category is expected and correct when
it doesn't apply. Do not pad a category with generic advice just to fill
it.

Respond with ONLY a JSON object matching this schema, no other text:
{"code_fixes": [{"description": string, "rationale": string}],
 "configuration_changes": [{"description": string, "rationale": string}],
 "database_improvements": [{"description": string, "rationale": string}]}

Each `rationale` must explain why that specific recommendation addresses
the root cause and its contributing factors — not just restate the
description."""


def build_recommendation_prompt(*, root_cause: RootCauseResult) -> str:
    return (
        f"Hypothesis: {root_cause.hypothesis}\n"
        f"Matched pattern: {root_cause.matched_pattern}\n"
        f"Confidence score: {root_cause.confidence_score}\n"
        f"Reasoning: {root_cause.reasoning}\n"
        f"Contributing factors: {root_cause.contributing_factors}"
    )


REPORT_SYSTEM_PROMPT = """\
You are the Report Agent in a production incident-investigation system.
The Root Cause, Evidence, Confidence, and Recommendation sections of the
final report are rendered separately, directly from data you're given
below — do not restate or summarize them. Your job is only:

- summary: a 2-4 sentence executive summary covering what happened, its
  impact, and the resolution direction, written for a mixed
  technical/non-technical audience.
- next_steps: a concrete, ordered action list for the team — ownership,
  monitoring, and process follow-ups (e.g. schedule a postmortem, watch a
  specific metric) — distinct from the code/config/database fixes already
  listed under Recommendation.

Respond with ONLY a JSON object matching this schema, no other text:
{"summary": string, "next_steps": [string]}"""


def build_report_prompt(
    *,
    monitoring_summary: str,
    log_analysis: LogAnalysisResult,
    root_cause: RootCauseResult,
    recommendations: RecommendationResult,
) -> str:
    return (
        f"Monitoring summary: {monitoring_summary}\n\n"
        f"Log analysis: {log_analysis.model_dump()}\n\n"
        f"Root cause: {root_cause.model_dump()}\n\n"
        f"Recommendations: {recommendations.model_dump()}"
    )

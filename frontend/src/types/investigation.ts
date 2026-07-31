import type { IncidentSeverity } from "@/types/incident";

/** Mirrors `backend/src/app/agents/state/investigation_state.py`. */

export interface MonitoringResult {
  incident_detected: boolean;
  severity: IncidentSeverity;
  summary: string;
  error_count: number;
  warning_count: number;
  sample_errors: string[];
  sample_warnings: string[];
}

export interface StackTrace {
  exception_type: string;
  message: string;
  raw_text: string;
}

export interface RepeatedFailure {
  signature: string;
  example_message: string;
  count: number;
  first_seen: string | null;
  last_seen: string | null;
}

export interface LogAnalysisResult {
  affected_components: string[];
  time_range: string;
  stack_traces: StackTrace[];
  repeated_failures: RepeatedFailure[];
  anomalies: string[];
}

export interface RootCauseResult {
  hypothesis: string;
  matched_pattern: string | null;
  confidence_score: number;
  reasoning: string;
  contributing_factors: string[];
}

export interface Recommendation {
  description: string;
  rationale: string;
}

export interface RecommendationResult {
  code_fixes: Recommendation[];
  configuration_changes: Recommendation[];
  database_improvements: Recommendation[];
}

export interface InvestigationState {
  logs: string;
  monitoring: MonitoringResult | null;
  log_analysis: LogAnalysisResult | null;
  root_cause: RootCauseResult | null;
  recommendations: RecommendationResult | null;
  report: string | null;
  incident_id: string | null;
}

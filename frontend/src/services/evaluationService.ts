import { apiClient } from "@/services/apiClient";
import type { EvaluationResult, EvaluationSummary } from "@/types/evaluation";

export function getEvaluationSummary(): Promise<EvaluationSummary> {
  return apiClient.get<EvaluationSummary>("/evaluations/summary");
}

/** Lists every stored evaluation, most recently evaluated first. */
export function getEvaluations(): Promise<EvaluationResult[]> {
  return apiClient.get<EvaluationResult[]>("/evaluations");
}

/** Returns one incident's evaluation (response time, confidence, quality scores). */
export function getEvaluation(incidentId: string): Promise<EvaluationResult> {
  return apiClient.get<EvaluationResult>(`/evaluations/${encodeURIComponent(incidentId)}`);
}

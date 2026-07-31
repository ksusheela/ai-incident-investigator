import { apiClient } from "@/services/apiClient";
import type { InvestigationState } from "@/types/investigation";

/** Runs the Monitoring -> Log Analysis -> Root Cause -> Recommendation -> Report
 * pipeline over raw log text and returns the final state. */
export function runInvestigation(logs: string): Promise<InvestigationState> {
  return apiClient.post<InvestigationState>("/investigations", { logs });
}

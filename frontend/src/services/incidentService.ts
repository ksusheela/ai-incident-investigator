import { apiClient } from "@/services/apiClient";
import type { IncidentSummary } from "@/types/incident";

/** Lists confirmed incidents, most recently created first. */
export function getIncidents(): Promise<IncidentSummary[]> {
  return apiClient.get<IncidentSummary[]>("/incidents");
}

/** Returns the persisted Markdown report for one incident. */
export function getIncidentReport(incidentId: string): Promise<string> {
  return apiClient.getText(`/incidents/${encodeURIComponent(incidentId)}/report`);
}

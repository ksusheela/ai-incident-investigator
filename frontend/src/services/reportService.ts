import { apiClient } from "@/services/apiClient";
import type { IncidentReport } from "@/types/report";

/** Calls the backend's future reports endpoint (not yet implemented server-side). */
export function getReports(): Promise<IncidentReport[]> {
  return apiClient.get<IncidentReport[]>("/reports");
}

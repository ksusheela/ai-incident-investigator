import { apiClient } from "@/services/apiClient";
import type { Incident } from "@/types/incident";

/** Calls the backend's future incidents endpoint (not yet implemented server-side). */
export function getIncidents(): Promise<Incident[]> {
  return apiClient.get<Incident[]>("/incidents");
}

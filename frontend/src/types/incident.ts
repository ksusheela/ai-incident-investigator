/** Mirrors `IncidentSummary` in `backend/src/app/api/incidents.py`. */
export type IncidentSeverity = "none" | "low" | "medium" | "high" | "critical";

export interface IncidentSummary {
  incident_id: string;
  created_at: string;
  severity: IncidentSeverity;
  summary: string;
}

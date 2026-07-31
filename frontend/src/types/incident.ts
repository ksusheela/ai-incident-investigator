export type IncidentSeverity = "low" | "medium" | "high" | "critical";
export type IncidentStatus = "open" | "investigating" | "resolved";

/**
 * Provisional shape — the backend does not expose an incidents endpoint yet
 * (planned for the log-upload/detection feature). This contract will be
 * finalized against the real API response when that lands.
 */
export interface Incident {
  id: string;
  title: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  createdAt: string;
}

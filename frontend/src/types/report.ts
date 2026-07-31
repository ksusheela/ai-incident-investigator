/**
 * Provisional shape — the backend does not expose a reports endpoint yet
 * (planned for the incident-report-generation feature). This contract will
 * be finalized against the real API response when that lands.
 */
export interface IncidentReport {
  id: string;
  incidentId: string;
  title: string;
  summary: string;
  generatedAt: string;
}

import { useState } from "react";

import { AsyncSection } from "@/components/common/AsyncSection";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { ReportViewer } from "@/components/incidents/ReportViewer";
import { useAsync } from "@/hooks/useAsync";
import { getIncidentReport, getIncidents } from "@/services/incidentService";
import { formatIncidentTimestamp } from "@/utils/formatIncidentTimestamp";

interface IncidentReportBrowserProps {
  title: string;
  emptyMessage: string;
}

/**
 * Lists confirmed incidents and lets the reader pull up any one's
 * persisted Markdown report on demand. Shared by the Reports page (whose
 * whole job is browsing reports) and the Incident Analysis page (which
 * shows it below the "run a new analysis" form for context).
 */
export function IncidentReportBrowser({ title, emptyMessage }: IncidentReportBrowserProps) {
  const incidents = useAsync(getIncidents, []);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [report, setReport] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);

  async function viewReport(incidentId: string) {
    setSelectedId(incidentId);
    setReport(null);
    setReportError(null);
    setLoadingReport(true);
    try {
      setReport(await getIncidentReport(incidentId));
    } catch (err) {
      setReportError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingReport(false);
    }
  }

  return (
    <div className="card">
      <div className="card-body">
        <h2 className="h6 card-title">{title}</h2>

        <AsyncSection
          state={incidents}
          errorTitle="Incidents unavailable"
          loadingLabel="Loading incidents…"
          isEmpty={(data) => data.length === 0}
          emptyMessage={emptyMessage}
        >
          {(data) => (
            <div className="table-responsive">
              <table className="table table-hover align-middle">
                <thead>
                  <tr>
                    <th scope="col">Created</th>
                    <th scope="col">Severity</th>
                    <th scope="col">Summary</th>
                    <th scope="col" />
                  </tr>
                </thead>
                <tbody>
                  {data.map((incident) => (
                    <tr key={incident.incident_id}>
                      <td className="small">{formatIncidentTimestamp(incident.created_at)}</td>
                      <td>
                        <SeverityBadge severity={incident.severity} />
                      </td>
                      <td className="small">{incident.summary}</td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-sm btn-outline-secondary"
                          onClick={() => viewReport(incident.incident_id)}
                        >
                          View report
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </AsyncSection>

        {selectedId && (
          <div className="mt-3">
            {loadingReport && <LoadingSpinner label="Loading report…" />}
            {reportError && <ErrorAlert title="Report unavailable" message={reportError} />}
            {report && <ReportViewer markdown={report} />}
          </div>
        )}
      </div>
    </div>
  );
}

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { useAsync } from "@/hooks/useAsync";
import { getIncidents } from "@/services/incidentService";

export function IncidentsPage() {
  const incidents = useAsync(getIncidents, []);

  return (
    <div>
      <h1 className="h4 mb-3">Incidents</h1>

      {incidents.status === "loading" && <LoadingSpinner label="Loading incidents…" />}

      {incidents.status === "error" && (
        <ErrorAlert
          title="Incidents service not available yet"
          message="The backend does not expose an incidents endpoint yet — this lands with the log-upload/detection feature."
        />
      )}

      {incidents.status === "success" && incidents.data.length === 0 && (
        <EmptyState message="No incidents recorded." />
      )}

      {incidents.status === "success" && incidents.data.length > 0 && (
        <div className="table-responsive">
          <table className="table table-hover align-middle">
            <thead>
              <tr>
                <th scope="col">Title</th>
                <th scope="col">Severity</th>
                <th scope="col">Status</th>
                <th scope="col">Created</th>
              </tr>
            </thead>
            <tbody>
              {incidents.data.map((incident) => (
                <tr key={incident.id}>
                  <td>{incident.title}</td>
                  <td className="text-capitalize">{incident.severity}</td>
                  <td className="text-capitalize">{incident.status}</td>
                  <td>{new Date(incident.createdAt).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { useAsync } from "@/hooks/useAsync";
import { getHealth } from "@/services/healthService";
import { getIncidents } from "@/services/incidentService";

function SystemStatusCard() {
  const health = useAsync(getHealth, []);

  return (
    <div className="card h-100">
      <div className="card-body">
        <h2 className="h6 card-title">System status</h2>
        {health.status === "loading" && <LoadingSpinner label="Checking backend…" />}
        {health.status === "error" && (
          <ErrorAlert title="Backend unreachable" message={health.error.message} />
        )}
        {health.status === "success" && (
          <dl className="row mb-0 small">
            <dt className="col-5">Status</dt>
            <dd className="col-7 text-capitalize">{health.data.status}</dd>
            <dt className="col-5">Version</dt>
            <dd className="col-7">{health.data.app_version}</dd>
            <dt className="col-5">Environment</dt>
            <dd className="col-7">{health.data.app_env}</dd>
            <dt className="col-5">Database</dt>
            <dd className="col-7">{health.data.db_connected ? "connected" : "unavailable"}</dd>
          </dl>
        )}
      </div>
    </div>
  );
}

function RecentIncidentsCard() {
  const incidents = useAsync(getIncidents, []);

  return (
    <div className="card h-100">
      <div className="card-body">
        <h2 className="h6 card-title">Recent incidents</h2>
        {incidents.status === "loading" && <LoadingSpinner />}
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
          <ul className="list-group list-group-flush">
            {incidents.data.map((incident) => (
              <li key={incident.id} className="list-group-item d-flex justify-content-between">
                <span>{incident.title}</span>
                <span className="badge text-bg-secondary text-capitalize">{incident.severity}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function DashboardPage() {
  return (
    <div>
      <h1 className="h4 mb-3">Dashboard</h1>
      <div className="row g-3">
        <div className="col-12 col-md-6">
          <SystemStatusCard />
        </div>
        <div className="col-12 col-md-6">
          <RecentIncidentsCard />
        </div>
      </div>
    </div>
  );
}

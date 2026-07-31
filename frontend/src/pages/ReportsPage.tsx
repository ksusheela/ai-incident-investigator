import { EmptyState } from "@/components/common/EmptyState";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { useAsync } from "@/hooks/useAsync";
import { getReports } from "@/services/reportService";

export function ReportsPage() {
  const reports = useAsync(getReports, []);

  return (
    <div>
      <h1 className="h4 mb-3">Reports</h1>

      {reports.status === "loading" && <LoadingSpinner label="Loading reports…" />}

      {reports.status === "error" && (
        <ErrorAlert
          title="Reports service not available yet"
          message="The backend does not expose a reports endpoint yet — this lands with the incident-report-generation feature."
        />
      )}

      {reports.status === "success" && reports.data.length === 0 && (
        <EmptyState message="No reports generated yet." />
      )}

      {reports.status === "success" && reports.data.length > 0 && (
        <div className="list-group">
          {reports.data.map((report) => (
            <div key={report.id} className="list-group-item">
              <div className="d-flex justify-content-between">
                <h2 className="h6 mb-1">{report.title}</h2>
                <small className="text-secondary">
                  {new Date(report.generatedAt).toLocaleString()}
                </small>
              </div>
              <p className="mb-0 small text-secondary">{report.summary}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

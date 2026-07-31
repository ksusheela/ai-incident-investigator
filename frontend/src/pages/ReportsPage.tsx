import { IncidentReportBrowser } from "@/components/incidents/IncidentReportBrowser";

export function ReportsPage() {
  return (
    <div>
      <h1 className="h4 mb-3">Reports</h1>
      <IncidentReportBrowser
        title="Incident reports"
        emptyMessage="No reports generated yet — run an analysis from Incident Analysis."
      />
    </div>
  );
}

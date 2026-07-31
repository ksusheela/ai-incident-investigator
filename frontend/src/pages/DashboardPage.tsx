import { BarChart, type BarChartDatum } from "@/components/charts/BarChart";
import { AsyncSection } from "@/components/common/AsyncSection";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { useAsync } from "@/hooks/useAsync";
import { getEvaluationSummary } from "@/services/evaluationService";
import { getHealth } from "@/services/healthService";
import { getIncidents } from "@/services/incidentService";
import type { IncidentSeverity, IncidentSummary } from "@/types/incident";
import { formatIncidentTimestamp } from "@/utils/formatIncidentTimestamp";
import { formatPercent, formatSeconds } from "@/utils/format";

const SEVERITY_ORDER: IncidentSeverity[] = ["none", "low", "medium", "high", "critical"];
const SEVERITY_COLOR_VAR: Record<IncidentSeverity, string> = {
  none: "--viz-status-neutral",
  low: "--viz-status-good",
  medium: "--viz-status-warning",
  high: "--viz-status-serious",
  critical: "--viz-status-critical",
};

function severityDistribution(incidents: IncidentSummary[]): BarChartDatum[] {
  const counts = new Map<IncidentSeverity, number>(SEVERITY_ORDER.map((severity) => [severity, 0]));
  for (const incident of incidents) {
    counts.set(incident.severity, (counts.get(incident.severity) ?? 0) + 1);
  }
  return SEVERITY_ORDER.map((severity) => ({
    label: severity,
    value: counts.get(severity) ?? 0,
    colorVar: SEVERITY_COLOR_VAR[severity],
  }));
}

function SystemStatusCard() {
  const health = useAsync(getHealth, []);

  return (
    <div className="card h-100">
      <div className="card-body">
        <h2 className="h6 card-title">System status</h2>
        <AsyncSection state={health} errorTitle="Backend unreachable" loadingLabel="Checking backend…">
          {(data) => (
            <dl className="row mb-0 small">
              <dt className="col-5">Status</dt>
              <dd className="col-7 text-capitalize">{data.status}</dd>
              <dt className="col-5">Version</dt>
              <dd className="col-7">{data.app_version}</dd>
              <dt className="col-5">Environment</dt>
              <dd className="col-7">{data.app_env}</dd>
              <dt className="col-5">Database</dt>
              <dd className="col-7">{data.db_connected ? "connected" : "unavailable"}</dd>
            </dl>
          )}
        </AsyncSection>
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
        <AsyncSection
          state={incidents}
          errorTitle="Incidents unavailable"
          isEmpty={(data) => data.length === 0}
          emptyMessage="No incidents recorded."
        >
          {(data) => (
            <ul className="list-group list-group-flush">
              {data.slice(0, 5).map((incident) => (
                <li
                  key={incident.incident_id}
                  className="list-group-item d-flex justify-content-between align-items-start gap-2"
                >
                  <div>
                    <div className="small">{incident.summary}</div>
                    <div className="small text-secondary">
                      {formatIncidentTimestamp(incident.created_at)}
                    </div>
                  </div>
                  <SeverityBadge severity={incident.severity} />
                </li>
              ))}
            </ul>
          )}
        </AsyncSection>
      </div>
    </div>
  );
}

function SeverityDistributionCard() {
  const incidents = useAsync(getIncidents, []);

  return (
    <div className="card h-100">
      <div className="card-body">
        <h2 className="h6 card-title">Incidents by severity</h2>
        <AsyncSection
          state={incidents}
          errorTitle="Incidents unavailable"
          isEmpty={(data) => data.length === 0}
          emptyMessage="No incidents recorded."
        >
          {(data) => {
            const distribution = severityDistribution(data);
            return (
              <BarChart
                data={distribution}
                maxValue={Math.max(...distribution.map((d) => d.value), 1)}
                ariaLabel="Number of stored incidents at each severity level"
              />
            );
          }}
        </AsyncSection>
      </div>
    </div>
  );
}

function EvaluationSummaryCard() {
  const evaluation = useAsync(getEvaluationSummary, []);

  return (
    <div className="card h-100">
      <div className="card-body">
        <h2 className="h6 card-title">Evaluation</h2>
        <AsyncSection
          state={evaluation}
          errorTitle="Evaluation summary unavailable"
          loadingLabel="Loading evaluation summary…"
          isEmpty={(data) => data.evaluated_count === 0}
          emptyMessage="No incidents evaluated yet."
        >
          {(data) => (
            <dl className="row mb-0 small">
              <dt className="col-7">Incidents evaluated</dt>
              <dd className="col-5">{data.evaluated_count}</dd>
              <dt className="col-7">Avg. response time</dt>
              <dd className="col-5">{formatSeconds(data.avg_response_time_seconds)}</dd>
              <dt className="col-7">Avg. confidence</dt>
              <dd className="col-5">{formatPercent(data.avg_confidence_score)}</dd>
              <dt className="col-7">Root cause quality</dt>
              <dd className="col-5">{formatPercent(data.avg_root_cause_quality)}</dd>
              <dt className="col-7">Recommendation quality</dt>
              <dd className="col-5">{formatPercent(data.avg_recommendation_quality)}</dd>
            </dl>
          )}
        </AsyncSection>
      </div>
    </div>
  );
}

export function DashboardPage() {
  return (
    <div>
      <h1 className="h4 mb-3">Dashboard</h1>
      <div className="row g-3 mb-3">
        <div className="col-12 col-md-6 col-lg-4">
          <SystemStatusCard />
        </div>
        <div className="col-12 col-md-6 col-lg-4">
          <RecentIncidentsCard />
        </div>
        <div className="col-12 col-md-6 col-lg-4">
          <EvaluationSummaryCard />
        </div>
      </div>
      <div className="row g-3">
        <div className="col-12">
          <SeverityDistributionCard />
        </div>
      </div>
    </div>
  );
}

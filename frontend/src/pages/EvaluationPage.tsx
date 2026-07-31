import { BarChart, type BarChartDatum } from "@/components/charts/BarChart";
import { AsyncSection } from "@/components/common/AsyncSection";
import { useAsync } from "@/hooks/useAsync";
import { getEvaluationSummary, getEvaluations } from "@/services/evaluationService";
import type { EvaluationSummary } from "@/types/evaluation";
import { formatPercent, formatSeconds } from "@/utils/format";

function qualityChartData(summary: EvaluationSummary): BarChartDatum[] {
  return [
    { label: "Confidence", value: Math.round((summary.avg_confidence_score ?? 0) * 100), colorVar: "--viz-sequential" },
    {
      label: "Root cause quality",
      value: Math.round((summary.avg_root_cause_quality ?? 0) * 100),
      colorVar: "--viz-sequential",
    },
    {
      label: "Recommendation quality",
      value: Math.round((summary.avg_recommendation_quality ?? 0) * 100),
      colorVar: "--viz-sequential",
    },
  ];
}

function SummaryCard() {
  const summary = useAsync(getEvaluationSummary, []);

  return (
    <div className="card mb-3">
      <div className="card-body">
        <h2 className="h6 card-title">Aggregate quality</h2>
        <AsyncSection
          state={summary}
          errorTitle="Evaluation summary unavailable"
          loadingLabel="Loading evaluation summary…"
          isEmpty={(data) => data.evaluated_count === 0}
          emptyMessage="No incidents evaluated yet."
        >
          {(data) => (
            <div className="row g-3 align-items-center">
              <div className="col-12 col-lg-5">
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
              </div>
              <div className="col-12 col-lg-7">
                <BarChart
                  data={qualityChartData(data)}
                  maxValue={100}
                  valueFormatter={(value) => `${value}%`}
                  ariaLabel="Average confidence, root cause quality, and recommendation quality across every evaluated incident"
                />
              </div>
            </div>
          )}
        </AsyncSection>
      </div>
    </div>
  );
}

function EvaluationsTable() {
  const evaluations = useAsync(getEvaluations, []);

  return (
    <div className="card">
      <div className="card-body">
        <h2 className="h6 card-title">Every evaluated incident</h2>
        <AsyncSection
          state={evaluations}
          errorTitle="Evaluations unavailable"
          loadingLabel="Loading evaluations…"
          isEmpty={(data) => data.length === 0}
          emptyMessage="No incidents evaluated yet."
        >
          {(data) => (
            <div className="table-responsive">
              <table className="table table-hover align-middle">
                <thead>
                  <tr>
                    <th scope="col">Incident</th>
                    <th scope="col">Evaluated at</th>
                    <th scope="col">Response time</th>
                    <th scope="col">Confidence</th>
                    <th scope="col">Root cause quality</th>
                    <th scope="col">Recommendation quality</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((evaluation) => (
                    <tr key={evaluation.incident_id}>
                      <td className="small text-truncate" style={{ maxWidth: "220px" }}>
                        {evaluation.incident_id}
                      </td>
                      <td className="small">{new Date(evaluation.evaluated_at).toLocaleString()}</td>
                      <td>{evaluation.response_time_seconds.toFixed(2)}s</td>
                      <td>{Math.round(evaluation.confidence_score * 100)}%</td>
                      <td>{Math.round(evaluation.root_cause_quality.score * 100)}%</td>
                      <td>{Math.round(evaluation.recommendation_quality.score * 100)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </AsyncSection>
      </div>
    </div>
  );
}

export function EvaluationPage() {
  return (
    <div>
      <h1 className="h4 mb-3">Evaluation</h1>
      <SummaryCard />
      <EvaluationsTable />
    </div>
  );
}

import { useState, type FormEvent } from "react";

import { IncidentReportBrowser } from "@/components/incidents/IncidentReportBrowser";
import { ReportViewer } from "@/components/incidents/ReportViewer";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { runInvestigation } from "@/services/investigationService";
import type { InvestigationState, Recommendation } from "@/types/investigation";

/** Keeps the downloaded filename to safe characters -- `incident_id` comes
 * from the backend response, and while it isn't markup (so not an XSS
 * vector as a download attribute), a malformed id shouldn't be able to
 * inject path separators or control characters into a suggested filename. */
function sanitizeFilenameSegment(value: string): string {
  return value.replace(/[^a-zA-Z0-9._-]/g, "_");
}

function downloadMarkdown(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = sanitizeFilenameSegment(filename);
  link.click();
  URL.revokeObjectURL(url);
}

function AnalysisForm({ onResult }: { onResult: (result: InvestigationState) => void }) {
  const [logs, setLogs] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await runInvestigation(logs);
      onResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card mb-3">
      <div className="card-body">
        <h2 className="h6 card-title">Run a new analysis</h2>
        <p className="small text-secondary">
          Paste raw application log text below. It runs through the full Monitoring &rarr; Log
          Analysis &rarr; Root Cause &rarr; Recommendation &rarr; Report pipeline.
        </p>
        <form onSubmit={handleSubmit}>
          <textarea
            className="form-control mb-2"
            rows={8}
            placeholder="ERROR checkout-service: 500&#10;ERROR checkout-service: db timeout&#10;…"
            value={logs}
            onChange={(event) => setLogs(event.target.value)}
            required
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting || logs.trim().length === 0}
          >
            {submitting && (
              <span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />
            )}
            {submitting ? "Analyzing…" : "Run analysis"}
          </button>
        </form>
        {error && (
          <div className="mt-3">
            <ErrorAlert title="Analysis failed" message={error} />
          </div>
        )}
      </div>
    </div>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const percent = Math.round(value * 100);
  return (
    <div
      className="progress"
      role="progressbar"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
      style={{ height: "10px" }}
    >
      <div className="progress-bar" style={{ width: `${percent}%` }} />
    </div>
  );
}

function RecommendationGroup({ title, items }: { title: string; items: Recommendation[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mb-3">
      <h3 className="h6 text-secondary">{title}</h3>
      <ul className="list-group list-group-flush">
        {items.map((item) => (
          <li key={item.description} className="list-group-item px-0">
            <div>{item.description}</div>
            <div className="small text-secondary">{item.rationale}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AnalysisResult({ result }: { result: InvestigationState }) {
  const { monitoring, log_analysis: logAnalysis, root_cause: rootCause, recommendations } = result;
  if (!monitoring) return null;

  return (
    <div className="d-flex flex-column gap-3 mb-4">
      <div className="card">
        <div className="card-body">
          <div className="d-flex justify-content-between align-items-start mb-2">
            <h2 className="h6 card-title mb-0">Monitoring</h2>
            <SeverityBadge severity={monitoring.severity} />
          </div>
          <p className="mb-2">{monitoring.summary}</p>
          <dl className="row mb-0 small">
            <dt className="col-6 col-sm-3">Errors</dt>
            <dd className="col-6 col-sm-3">{monitoring.error_count}</dd>
            <dt className="col-6 col-sm-3">Warnings</dt>
            <dd className="col-6 col-sm-3">{monitoring.warning_count}</dd>
          </dl>
        </div>
      </div>

      {!monitoring.incident_detected && (
        <EmptyState message="No incident detected in these logs — nothing further to analyze." />
      )}

      {logAnalysis && (
        <div className="card">
          <div className="card-body">
            <h2 className="h6 card-title">Log analysis</h2>
            <p className="small text-secondary mb-2">
              Time range: {logAnalysis.time_range || "—"}
            </p>
            {logAnalysis.affected_components.length > 0 && (
              <p className="mb-3">
                {logAnalysis.affected_components.map((component) => (
                  <span key={component} className="badge text-bg-secondary me-1">
                    {component}
                  </span>
                ))}
              </p>
            )}
            {logAnalysis.repeated_failures.length > 0 && (
              <div className="table-responsive mb-2">
                <table className="table table-sm align-middle">
                  <thead>
                    <tr>
                      <th scope="col">Signature</th>
                      <th scope="col">Example</th>
                      <th scope="col">Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logAnalysis.repeated_failures.map((failure) => (
                      <tr key={failure.signature}>
                        <td className="small">{failure.signature}</td>
                        <td className="small">{failure.example_message}</td>
                        <td>{failure.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {logAnalysis.anomalies.length > 0 && (
              <ul className="mb-0 small">
                {logAnalysis.anomalies.map((anomaly) => (
                  <li key={anomaly}>{anomaly}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {rootCause && (
        <div className="card">
          <div className="card-body">
            <h2 className="h6 card-title">Root cause</h2>
            <p className="mb-2">{rootCause.hypothesis}</p>
            <div className="mb-3">
              <div className="d-flex justify-content-between small text-secondary mb-1">
                <span>Confidence</span>
                <span>{Math.round(rootCause.confidence_score * 100)}%</span>
              </div>
              <ConfidenceBar value={rootCause.confidence_score} />
            </div>
            {rootCause.matched_pattern && (
              <p className="small mb-2">
                <span className="text-secondary">Matched pattern: </span>
                <code>{rootCause.matched_pattern}</code>
              </p>
            )}
            <p className="small mb-2">{rootCause.reasoning}</p>
            {rootCause.contributing_factors.length > 0 && (
              <ul className="small mb-0">
                {rootCause.contributing_factors.map((factor) => (
                  <li key={factor}>{factor}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {recommendations && (
        <div className="card">
          <div className="card-body">
            <h2 className="h6 card-title">Recommendations</h2>
            <RecommendationGroup title="Code fixes" items={recommendations.code_fixes} />
            <RecommendationGroup
              title="Configuration changes"
              items={recommendations.configuration_changes}
            />
            <RecommendationGroup
              title="Database improvements"
              items={recommendations.database_improvements}
            />
          </div>
        </div>
      )}

      {result.report && (
        <div className="card">
          <div className="card-body">
            <div className="d-flex justify-content-between align-items-center mb-2">
              <h2 className="h6 card-title mb-0">Report</h2>
              <button
                type="button"
                className="btn btn-sm btn-outline-secondary"
                onClick={() =>
                  downloadMarkdown(`${result.incident_id ?? "incident"}-report.md`, result.report!)
                }
              >
                Download .md
              </button>
            </div>
            <ReportViewer markdown={result.report} />
          </div>
        </div>
      )}
    </div>
  );
}

export function IncidentAnalysisPage() {
  const [result, setResult] = useState<InvestigationState | null>(null);

  return (
    <div>
      <h1 className="h4 mb-3">Incident Analysis</h1>
      <AnalysisForm onResult={setResult} />
      {result && <AnalysisResult result={result} />}
      <IncidentReportBrowser
        title="Past incidents"
        emptyMessage="No incidents recorded yet — run an analysis above."
      />
    </div>
  );
}

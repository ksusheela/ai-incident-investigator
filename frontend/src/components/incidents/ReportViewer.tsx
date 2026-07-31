interface ReportViewerProps {
  markdown: string;
}

/** Renders a persisted incident report's raw Markdown as preformatted
 * text -- shared by `IncidentAnalysisPage` (a just-run analysis) and
 * `IncidentReportBrowser` (a report fetched on demand), which previously
 * duplicated this exact block. */
export function ReportViewer({ markdown }: ReportViewerProps) {
  return (
    <pre className="small bg-body-tertiary border rounded-3 p-3 mb-0" style={{ whiteSpace: "pre-wrap" }}>
      {markdown}
    </pre>
  );
}

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IncidentAnalysisPage } from "@/pages/IncidentAnalysisPage";

vi.mock("@/services/incidentService", () => ({
  getIncidents: vi.fn(),
  getIncidentReport: vi.fn(),
}));
vi.mock("@/services/investigationService", () => ({
  runInvestigation: vi.fn(),
}));

import { getIncidents } from "@/services/incidentService";
import { runInvestigation } from "@/services/investigationService";

const mockedGetIncidents = vi.mocked(getIncidents);
const mockedRunInvestigation = vi.mocked(runInvestigation);

describe("IncidentAnalysisPage", () => {
  beforeEach(() => {
    mockedGetIncidents.mockReset().mockResolvedValue([]);
    mockedRunInvestigation.mockReset();
  });

  it("runs an analysis and renders the resulting root cause and recommendations", async () => {
    const user = userEvent.setup();
    mockedRunInvestigation.mockResolvedValue({
      logs: "ERROR db timeout",
      monitoring: {
        incident_detected: true,
        severity: "high",
        summary: "Detected 1 error line(s); severity: high.",
        error_count: 1,
        warning_count: 0,
        sample_errors: ["ERROR db timeout"],
        sample_warnings: [],
      },
      log_analysis: {
        affected_components: ["checkout-service"],
        time_range: "12:00-12:05",
        stack_traces: [],
        repeated_failures: [],
        anomalies: [],
      },
      root_cause: {
        hypothesis: "connection pool exhaustion",
        matched_pattern: "connection_pool_exhaustion",
        confidence_score: 0.85,
        reasoning: "Repeated timeouts indicate exhaustion.",
        contributing_factors: ["undersized pool"],
      },
      recommendations: {
        code_fixes: [],
        configuration_changes: [{ description: "Increase pool size", rationale: "Undersized." }],
        database_improvements: [],
      },
      report: "# Incident Report\n\nSummary here.",
      incident_id: "20260731T120000000000Z-aaaaaaaa",
    });

    render(<IncidentAnalysisPage />);

    await user.type(screen.getByPlaceholderText(/ERROR checkout-service/), "ERROR db timeout");
    await user.click(screen.getByRole("button", { name: "Run analysis" }));

    expect(await screen.findByText("connection pool exhaustion")).toBeInTheDocument();
    expect(screen.getByText("Increase pool size")).toBeInTheDocument();
    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it("shows an error alert when the analysis request fails", async () => {
    const user = userEvent.setup();
    mockedRunInvestigation.mockRejectedValue(new Error("backend unavailable"));

    render(<IncidentAnalysisPage />);

    await user.type(screen.getByPlaceholderText(/ERROR checkout-service/), "ERROR db timeout");
    await user.click(screen.getByRole("button", { name: "Run analysis" }));

    expect(await screen.findByText("Analysis failed")).toBeInTheDocument();
    expect(screen.getByText("backend unavailable")).toBeInTheDocument();
  });
});

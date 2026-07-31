import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReportsPage } from "@/pages/ReportsPage";

vi.mock("@/services/incidentService", () => ({
  getIncidents: vi.fn(),
  getIncidentReport: vi.fn(),
}));

import { getIncidentReport, getIncidents } from "@/services/incidentService";

const mockedGetIncidents = vi.mocked(getIncidents);
const mockedGetIncidentReport = vi.mocked(getIncidentReport);

describe("ReportsPage / IncidentReportBrowser", () => {
  beforeEach(() => {
    mockedGetIncidents.mockReset();
    mockedGetIncidentReport.mockReset();
  });

  it("shows an empty state when there are no incidents", async () => {
    mockedGetIncidents.mockResolvedValue([]);

    render(<ReportsPage />);

    expect(
      await screen.findByText("No reports generated yet — run an analysis from Incident Analysis."),
    ).toBeInTheDocument();
  });

  it("lists incidents and fetches a report on demand", async () => {
    const user = userEvent.setup();
    mockedGetIncidents.mockResolvedValue([
      {
        incident_id: "20260731T120000000000Z-aaaaaaaa",
        created_at: "20260731T120000000000Z",
        severity: "high",
        summary: "Checkout failures spiked",
      },
    ]);
    mockedGetIncidentReport.mockResolvedValue("# Incident Report\n\nSummary here.");

    render(<ReportsPage />);

    expect(await screen.findByText("Checkout failures spiked")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "View report" }));

    expect(await screen.findByText(/Summary here\./)).toBeInTheDocument();
    expect(mockedGetIncidentReport).toHaveBeenCalledWith("20260731T120000000000Z-aaaaaaaa");
  });

  it("shows an error alert when fetching a report fails", async () => {
    const user = userEvent.setup();
    mockedGetIncidents.mockResolvedValue([
      {
        incident_id: "20260731T120000000000Z-aaaaaaaa",
        created_at: "20260731T120000000000Z",
        severity: "high",
        summary: "Checkout failures spiked",
      },
    ]);
    mockedGetIncidentReport.mockRejectedValue(new Error("not found"));

    render(<ReportsPage />);
    await user.click(await screen.findByRole("button", { name: "View report" }));

    expect(await screen.findByText("Report unavailable")).toBeInTheDocument();
  });
});

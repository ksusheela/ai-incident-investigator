import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "@/pages/DashboardPage";

vi.mock("@/services/healthService", () => ({
  getHealth: vi.fn().mockRejectedValue(new Error("not needed for these tests")),
}));
vi.mock("@/services/incidentService", () => ({
  getIncidents: vi.fn(),
}));
vi.mock("@/services/evaluationService", () => ({
  getEvaluationSummary: vi.fn(),
}));

import { getIncidents } from "@/services/incidentService";
import { getEvaluationSummary } from "@/services/evaluationService";

const mockedGetIncidents = vi.mocked(getIncidents);
const mockedGetEvaluationSummary = vi.mocked(getEvaluationSummary);

describe("DashboardPage evaluation summary card", () => {
  beforeEach(() => {
    mockedGetEvaluationSummary.mockReset();
    mockedGetIncidents.mockReset().mockResolvedValue([]);
  });

  it("renders aggregate metrics once evaluations exist", async () => {
    mockedGetEvaluationSummary.mockResolvedValue({
      evaluated_count: 2,
      avg_response_time_seconds: 1.5,
      avg_confidence_score: 0.85,
      avg_root_cause_quality: 0.75,
      avg_recommendation_quality: 1.0,
    });

    render(<DashboardPage />);

    expect(await screen.findByText("2")).toBeInTheDocument();
    expect(screen.getByText("1.50s")).toBeInTheDocument();
    expect(screen.getByText("85%")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("shows an empty state when no incidents have been evaluated", async () => {
    mockedGetEvaluationSummary.mockResolvedValue({
      evaluated_count: 0,
      avg_response_time_seconds: null,
      avg_confidence_score: null,
      avg_root_cause_quality: null,
      avg_recommendation_quality: null,
    });

    render(<DashboardPage />);

    expect(await screen.findAllByText("No incidents evaluated yet.")).not.toHaveLength(0);
  });

  it("shows an error state when the evaluation summary request fails", async () => {
    mockedGetEvaluationSummary.mockRejectedValue(new Error("boom"));

    render(<DashboardPage />);

    expect(await screen.findByText("Evaluation summary unavailable")).toBeInTheDocument();
  });
});

describe("DashboardPage incidents", () => {
  beforeEach(() => {
    mockedGetEvaluationSummary.mockReset().mockResolvedValue({
      evaluated_count: 0,
      avg_response_time_seconds: null,
      avg_confidence_score: null,
      avg_root_cause_quality: null,
      avg_recommendation_quality: null,
    });
    mockedGetIncidents.mockReset();
  });

  it("lists recent incidents and charts the severity distribution", async () => {
    mockedGetIncidents.mockResolvedValue([
      {
        incident_id: "20260731T120000000000Z-aaaaaaaa",
        created_at: "20260731T120000000000Z",
        severity: "high",
        summary: "Checkout failures spiked",
      },
      {
        incident_id: "20260731T110000000000Z-bbbbbbbb",
        created_at: "20260731T110000000000Z",
        severity: "high",
        summary: "Payment timeouts",
      },
    ]);

    render(<DashboardPage />);

    expect(await screen.findByText("Checkout failures spiked")).toBeInTheDocument();
    const chartCard = screen.getByText("Incidents by severity").closest(".card");
    expect(chartCard).not.toBeNull();
    expect(within(chartCard as HTMLElement).getByText("2")).toBeInTheDocument();
    expect(within(chartCard as HTMLElement).getByText("high")).toBeInTheDocument();
  });

  it("shows an empty state when no incidents are recorded", async () => {
    mockedGetIncidents.mockResolvedValue([]);

    render(<DashboardPage />);

    expect(await screen.findAllByText("No incidents recorded.")).toHaveLength(2);
  });
});

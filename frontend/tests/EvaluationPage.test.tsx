import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EvaluationPage } from "@/pages/EvaluationPage";

vi.mock("@/services/evaluationService", () => ({
  getEvaluationSummary: vi.fn(),
  getEvaluations: vi.fn(),
}));

import { getEvaluationSummary, getEvaluations } from "@/services/evaluationService";

const mockedGetEvaluationSummary = vi.mocked(getEvaluationSummary);
const mockedGetEvaluations = vi.mocked(getEvaluations);

describe("EvaluationPage", () => {
  beforeEach(() => {
    mockedGetEvaluationSummary.mockReset();
    mockedGetEvaluations.mockReset();
  });

  it("shows empty states when nothing has been evaluated", async () => {
    mockedGetEvaluationSummary.mockResolvedValue({
      evaluated_count: 0,
      avg_response_time_seconds: null,
      avg_confidence_score: null,
      avg_root_cause_quality: null,
      avg_recommendation_quality: null,
    });
    mockedGetEvaluations.mockResolvedValue([]);

    render(<EvaluationPage />);

    expect(await screen.findAllByText("No incidents evaluated yet.")).toHaveLength(2);
  });

  it("renders the aggregate chart and the full evaluations table", async () => {
    mockedGetEvaluationSummary.mockResolvedValue({
      evaluated_count: 1,
      avg_response_time_seconds: 0.5,
      avg_confidence_score: 0.9,
      avg_root_cause_quality: 1.0,
      avg_recommendation_quality: 0.5,
    });
    mockedGetEvaluations.mockResolvedValue([
      {
        incident_id: "20260731T120000000000Z-aaaaaaaa",
        evaluated_at: "2026-07-31T12:00:05+00:00",
        response_time_seconds: 0.5,
        confidence_score: 0.9,
        root_cause_quality: { score: 1.0, checks: [] },
        recommendation_quality: { score: 0.5, checks: [] },
      },
    ]);

    render(<EvaluationPage />);

    expect(await screen.findByText("20260731T120000000000Z-aaaaaaaa")).toBeInTheDocument();
    expect(
      screen.getByRole("img", {
        name: "Average confidence, root cause quality, and recommendation quality across every evaluated incident",
      }),
    ).toBeInTheDocument();
  });
});

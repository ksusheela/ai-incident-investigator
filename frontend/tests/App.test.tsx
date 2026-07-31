import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "@/App";

vi.mock("@/services/healthService", () => ({
  getHealth: vi.fn().mockResolvedValue({
    status: "ok",
    app_name: "AI Incident Investigator",
    app_version: "0.1.0",
    app_env: "test",
    db_connected: true,
  }),
}));
vi.mock("@/services/incidentService", () => ({
  getIncidents: vi.fn().mockResolvedValue([]),
  getIncidentReport: vi.fn(),
}));
vi.mock("@/services/evaluationService", () => ({
  getEvaluationSummary: vi.fn().mockResolvedValue({
    evaluated_count: 0,
    avg_response_time_seconds: null,
    avg_confidence_score: null,
    avg_root_cause_quality: null,
    avg_recommendation_quality: null,
  }),
  getEvaluations: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/services/investigationService", () => ({
  runInvestigation: vi.fn(),
}));

describe("App routing", () => {
  it("navigates to every top-level page from the sidebar", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument();

    for (const label of ["Incident Analysis", "Reports", "Evaluation", "Settings"]) {
      await user.click(screen.getByRole("link", { name: label }));
      expect(await screen.findByRole("heading", { name: label })).toBeInTheDocument();
    }

    await user.click(screen.getByRole("link", { name: "Dashboard" }));
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
  });

  it("shows the 404 page for an unknown route", async () => {
    window.history.pushState({}, "", "/does-not-exist");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});

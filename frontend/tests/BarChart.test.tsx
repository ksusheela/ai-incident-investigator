import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { BarChart } from "@/components/charts/BarChart";

describe("BarChart", () => {
  it("direct-labels every bar's category and value", () => {
    render(
      <BarChart
        data={[
          { label: "none", value: 3, colorVar: "--viz-status-neutral" },
          { label: "critical", value: 1, colorVar: "--viz-status-critical" },
        ]}
        maxValue={3}
        ariaLabel="Test chart"
      />,
    );

    expect(screen.getByText("none")).toBeInTheDocument();
    expect(screen.getByText("critical")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("shows a tooltip with the category and value on hover", async () => {
    const user = userEvent.setup();
    render(
      <BarChart
        data={[{ label: "medium", value: 42, colorVar: "--viz-status-warning" }]}
        maxValue={100}
        valueFormatter={(value) => `${value}%`}
        ariaLabel="Test chart"
      />,
    );

    await user.hover(screen.getByRole("button", { name: "medium: 42%" }));

    expect(screen.getByText("medium: 42%")).toBeInTheDocument();
  });
});

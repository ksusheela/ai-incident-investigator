import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { Sidebar } from "@/components/layout/Sidebar";

describe("Sidebar", () => {
  it("renders a nav link for every top-level page", () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Incident Analysis" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Reports" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Evaluation" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Settings" })).toBeInTheDocument();
  });

  it("marks the current route's link as active", () => {
    render(
      <MemoryRouter initialEntries={["/incident-analysis"]}>
        <Sidebar />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Incident Analysis" })).toHaveClass("active");
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveClass("active");
  });
});

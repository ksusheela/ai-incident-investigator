import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SeverityBadge } from "@/components/common/SeverityBadge";

describe("SeverityBadge", () => {
  it.each(["none", "low", "medium", "high", "critical"] as const)(
    "renders the %s severity with its status color class",
    (severity) => {
      render(<SeverityBadge severity={severity} />);

      const badge = screen.getByText(severity);
      expect(badge).toHaveClass(`badge-severity-${severity}`);
    },
  );
});

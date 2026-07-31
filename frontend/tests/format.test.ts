import { describe, expect, it } from "vitest";

import { formatPercent, formatSeconds } from "@/utils/format";

describe("formatPercent", () => {
  it("renders a fraction as a rounded whole-number percentage", () => {
    expect(formatPercent(0.85)).toBe("85%");
    expect(formatPercent(0.666)).toBe("67%");
  });

  it("renders null as an em dash", () => {
    expect(formatPercent(null)).toBe("—");
  });
});

describe("formatSeconds", () => {
  it("renders a duration to two decimal places with an 's' suffix", () => {
    expect(formatSeconds(1.5)).toBe("1.50s");
    expect(formatSeconds(0.0223)).toBe("0.02s");
  });

  it("renders null as an em dash", () => {
    expect(formatSeconds(null)).toBe("—");
  });
});

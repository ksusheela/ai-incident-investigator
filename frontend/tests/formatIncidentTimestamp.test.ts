import { describe, expect, it } from "vitest";

import { formatIncidentTimestamp } from "@/utils/formatIncidentTimestamp";

describe("formatIncidentTimestamp", () => {
  it("parses the incident-id timestamp prefix into a locale date string", () => {
    const result = formatIncidentTimestamp("20260731T141243010542Z-aa9597af");

    expect(result).not.toBe("20260731T141243010542Z-aa9597af");
    expect(result).toContain("2026");
  });

  it("falls back to the raw value when it doesn't match the expected shape", () => {
    expect(formatIncidentTimestamp("not-a-timestamp")).toBe("not-a-timestamp");
    expect(formatIncidentTimestamp("")).toBe("");
  });
});

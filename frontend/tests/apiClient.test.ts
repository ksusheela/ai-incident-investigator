import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient, ApiError } from "@/services/apiClient";

const BASE_URL = "http://localhost:8000/api/v1"; // matches frontend/.env.test

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("apiClient", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("get() issues a GET request to the configured base URL and parses JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiClient.get<{ ok: boolean }>("/health");

    expect(result).toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE_URL}/health`);
    expect(init.method).toBe("GET");
  });

  it("post() sends a JSON body with the right method and content type", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ incident_id: "abc" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiClient.post<{ incident_id: string }>("/investigations", {
      logs: "ERROR x",
    });

    expect(result).toEqual({ incident_id: "abc" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE_URL}/investigations`);
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ logs: "ERROR x" });
  });

  it("getText() returns the raw response body as text", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("# Report\n", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiClient.getText("/incidents/abc/report");

    expect(result).toBe("# Report\n");
  });

  it("throws a typed ApiError with the status and path on a non-2xx response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("not found", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiClient.get("/incidents/missing")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      path: "/incidents/missing",
    });
    await expect(apiClient.get("/incidents/missing")).rejects.toBeInstanceOf(ApiError);
  });
});

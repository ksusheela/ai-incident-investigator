import { config } from "@/config";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly path: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function rawRequest(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, init);

  if (!response.ok) {
    throw new ApiError(
      `Request to ${path} failed with status ${response.status}`,
      response.status,
      path,
    );
  }

  return response;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await rawRequest(path, {
    headers: { Accept: "application/json", ...init?.headers },
    ...init,
  });
  return (await response.json()) as T;
}

async function requestText(path: string, init?: RequestInit): Promise<string> {
  const response = await rawRequest(path, init);
  return response.text();
}

/** Thin typed wrapper around `fetch`, pointed at the backend API base URL. */
export const apiClient = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  getText: (path: string) => requestText(path, { method: "GET" }),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};

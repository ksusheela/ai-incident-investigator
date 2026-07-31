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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    headers: { Accept: "application/json", ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    throw new ApiError(
      `Request to ${path} failed with status ${response.status}`,
      response.status,
      path,
    );
  }

  return (await response.json()) as T;
}

/** Thin typed wrapper around `fetch`, pointed at the backend API base URL. */
export const apiClient = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
};

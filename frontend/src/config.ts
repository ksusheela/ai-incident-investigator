/**
 * Runtime configuration sourced from Vite env vars (`VITE_*`).
 * Mirrors the backend's `Settings` pattern: one place that reads the
 * environment, validated once at startup instead of scattered
 * `import.meta.env` reads across the codebase.
 */

interface AppConfig {
  apiBaseUrl: string;
}

function readConfig(): AppConfig {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

  if (!apiBaseUrl) {
    throw new Error(
      "VITE_API_BASE_URL is not set. Copy frontend/.env.example to frontend/.env and set it.",
    );
  }

  return { apiBaseUrl };
}

export const config: AppConfig = readConfig();

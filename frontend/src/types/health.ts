/** Mirrors `HealthResponse` in `backend/src/app/api/health.py`. */
export interface HealthStatus {
  status: "ok" | "degraded";
  app_name: string;
  app_version: string;
  app_env: string;
  db_connected: boolean;
}

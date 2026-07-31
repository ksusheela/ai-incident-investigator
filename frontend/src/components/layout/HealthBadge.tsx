import { useAsync } from "@/hooks/useAsync";
import { getHealth } from "@/services/healthService";

/** Small live indicator in the top bar backed by the real `/health` endpoint. */
export function HealthBadge() {
  const state = useAsync(getHealth, []);

  if (state.status === "loading") {
    return <span className="badge text-bg-secondary">checking…</span>;
  }

  if (state.status === "error") {
    return <span className="badge text-bg-danger">API unreachable</span>;
  }

  const isOk = state.data.status === "ok";
  return (
    <span className={`badge ${isOk ? "text-bg-success" : "text-bg-warning"}`}>
      {isOk ? "operational" : "degraded"} · v{state.data.app_version}
    </span>
  );
}

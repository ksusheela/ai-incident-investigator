import { apiClient } from "@/services/apiClient";
import type { HealthStatus } from "@/types/health";

export function getHealth(): Promise<HealthStatus> {
  return apiClient.get<HealthStatus>("/health");
}

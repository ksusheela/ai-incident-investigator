import type { IncidentSeverity } from "@/types/incident";

interface SeverityBadgeProps {
  severity: IncidentSeverity;
}

/** Severity badge using the app's status palette (see `styles/custom.css`
 * `.badge-severity-*`) -- the same colors the severity chart uses, so
 * severity always reads the same way wherever it appears. */
export function SeverityBadge({ severity }: SeverityBadgeProps) {
  return <span className={`badge text-capitalize badge-severity-${severity}`}>{severity}</span>;
}

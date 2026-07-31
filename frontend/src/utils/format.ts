/** Shared display formatters for the evaluation metrics shown on both the
 * Dashboard and the Evaluation page. */

export function formatPercent(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}

export function formatSeconds(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(2)}s`;
}

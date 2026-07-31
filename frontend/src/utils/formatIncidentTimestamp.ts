/**
 * Parses the `created_at` prefix of an incident id -- `<UTC timestamp>-<hex>`,
 * e.g. `20260731T153000123456Z-a1b2c3d4` (see `generate_incident_id()` in
 * `backend/src/app/infrastructure/filesystem/artifact_store.py`) -- into a
 * locale-formatted date string. Falls back to the raw value if it doesn't
 * match the expected shape.
 */
export function formatIncidentTimestamp(createdAt: string): string {
  const match = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})/.exec(createdAt);
  if (!match) return createdAt;
  const [, year, month, day, hour, minute, second] = match;
  const date = new Date(`${year}-${month}-${day}T${hour}:${minute}:${second}Z`);
  return Number.isNaN(date.getTime()) ? createdAt : date.toLocaleString();
}

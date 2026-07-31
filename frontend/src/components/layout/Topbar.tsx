import { HealthBadge } from "@/components/layout/HealthBadge";

export function Topbar() {
  return (
    <nav className="navbar navbar-expand-lg border-bottom bg-body sticky-top px-3">
      <button
        type="button"
        className="btn btn-outline-secondary d-lg-none me-2"
        data-bs-toggle="offcanvas"
        data-bs-target="#sidebar"
        aria-controls="sidebar"
        aria-label="Toggle navigation"
      >
        <span aria-hidden="true">☰</span>
      </button>
      <span className="navbar-brand mb-0 h6 me-auto">AI Incident Investigator</span>
      <HealthBadge />
    </nav>
  );
}

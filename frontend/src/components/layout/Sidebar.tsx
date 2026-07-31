import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/incidents", label: "Incidents", end: false },
  { to: "/reports", label: "Reports", end: false },
  { to: "/settings", label: "Settings", end: false },
];

/**
 * Responsive sidebar using Bootstrap's `offcanvas-lg` pattern: a static
 * column at `lg` and above, an off-canvas panel (toggled via the Topbar's
 * hamburger button) below it. No custom show/hide state is needed — that's
 * handled by Bootstrap's own JS bundle via the `data-bs-*` attributes.
 */
export function Sidebar() {
  return (
    <div
      className="offcanvas-lg offcanvas-start bg-body-tertiary border-end"
      tabIndex={-1}
      id="sidebar"
      aria-labelledby="sidebarLabel"
      style={{ width: "240px" }}
    >
      <div className="offcanvas-header">
        <h6 className="offcanvas-title" id="sidebarLabel">
          Navigation
        </h6>
        <button
          type="button"
          className="btn-close"
          data-bs-dismiss="offcanvas"
          data-bs-target="#sidebar"
          aria-label="Close"
        />
      </div>
      <div className="offcanvas-body d-flex flex-column p-2 p-lg-3">
        <nav className="nav nav-pills flex-column gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              data-bs-dismiss="offcanvas"
              data-bs-target="#sidebar"
              className={({ isActive }) => `nav-link text-start ${isActive ? "active" : "text-body"}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}

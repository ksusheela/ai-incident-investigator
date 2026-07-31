import { config } from "@/config";
import { useTheme } from "@/store/themeContext";

export function SettingsPage() {
  const { theme, setTheme } = useTheme();

  return (
    <div>
      <h1 className="h4 mb-3">Settings</h1>

      <div className="card mb-3">
        <div className="card-body">
          <h2 className="h6 card-title">Appearance</h2>
          <div className="btn-group" role="group" aria-label="Theme">
            <button
              type="button"
              className={`btn btn-outline-secondary ${theme === "light" ? "active" : ""}`}
              aria-pressed={theme === "light"}
              onClick={() => setTheme("light")}
            >
              Light
            </button>
            <button
              type="button"
              className={`btn btn-outline-secondary ${theme === "dark" ? "active" : ""}`}
              aria-pressed={theme === "dark"}
              onClick={() => setTheme("dark")}
            >
              Dark
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-body">
          <h2 className="h6 card-title">Connection</h2>
          <dl className="row mb-0 small">
            <dt className="col-4 col-sm-3">API base URL</dt>
            <dd className="col-8 col-sm-9">
              <code>{config.apiBaseUrl}</code>
            </dd>
          </dl>
        </div>
      </div>
    </div>
  );
}

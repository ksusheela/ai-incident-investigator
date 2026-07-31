import { useEffect, useState, type ReactNode } from "react";

import { ThemeContext, type Theme } from "@/store/themeContext";

const STORAGE_KEY = "theme";

function getInitialTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * Drives Bootstrap 5.3's native color-mode support via the `data-bs-theme`
 * attribute on `<html>`, persisted to localStorage. No CSS variables need
 * overriding — Bootstrap's own dark-mode styles handle it.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-bs-theme", theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>;
}

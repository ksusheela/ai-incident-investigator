import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { ThemeProvider } from "@/store/ThemeProvider";
import { useTheme } from "@/store/themeContext";

function ThemeToggleProbe() {
  const { theme, setTheme } = useTheme();
  return (
    <div>
      <span data-testid="current-theme">{theme}</span>
      <button onClick={() => setTheme("dark")}>Dark</button>
      <button onClick={() => setTheme("light")}>Light</button>
    </div>
  );
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-bs-theme");
  });

  it("applies the selected theme to <html data-bs-theme> and persists it", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ThemeToggleProbe />
      </ThemeProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Dark" }));

    expect(screen.getByTestId("current-theme")).toHaveTextContent("dark");
    expect(document.documentElement.getAttribute("data-bs-theme")).toBe("dark");
    expect(localStorage.getItem("theme")).toBe("dark");
  });
});

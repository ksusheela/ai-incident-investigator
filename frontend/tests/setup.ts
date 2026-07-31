import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement matchMedia; ThemeProvider's system-preference
// detection needs it to exist even though tests don't rely on its result.
if (!window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}

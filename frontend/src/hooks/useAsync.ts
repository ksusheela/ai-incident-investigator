import { useEffect, useState } from "react";

export type AsyncState<T> =
  | { status: "loading"; data: undefined; error: undefined }
  | { status: "success"; data: T; error: undefined }
  | { status: "error"; data: undefined; error: Error };

/**
 * Runs `fetcher` once on mount (and whenever `deps` changes), tracking
 * loading/success/error state. Used by every page that calls the API
 * service layer, so each one gets consistent loading/error handling
 * without repeating the same three `useState` calls.
 */
export function useAsync<T>(fetcher: () => Promise<T>, deps: ReadonlyArray<unknown> = []): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({
    status: "loading",
    data: undefined,
    error: undefined,
  });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading", data: undefined, error: undefined });

    fetcher()
      .then((data) => {
        if (!cancelled) setState({ status: "success", data, error: undefined });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            data: undefined,
            error: error instanceof Error ? error : new Error(String(error)),
          });
        }
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}

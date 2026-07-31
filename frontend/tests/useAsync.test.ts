import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useAsync } from "@/hooks/useAsync";

describe("useAsync", () => {
  it("resolves to success state with the fetched data", async () => {
    const { result } = renderHook(() => useAsync(() => Promise.resolve({ value: 42 }), []));

    expect(result.current.status).toBe("loading");

    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.data).toEqual({ value: 42 });
  });

  it("resolves to error state when the fetcher rejects", async () => {
    const { result } = renderHook(() =>
      useAsync(() => Promise.reject(new Error("boom")), []),
    );

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error?.message).toBe("boom");
  });
});

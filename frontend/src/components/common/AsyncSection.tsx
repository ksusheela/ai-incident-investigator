import type { ReactNode } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import type { AsyncState } from "@/hooks/useAsync";

interface AsyncSectionProps<T> {
  state: AsyncState<T>;
  errorTitle: string;
  loadingLabel?: string;
  /** When it returns true for the resolved data, `emptyMessage` renders instead of `children`. */
  isEmpty?: (data: T) => boolean;
  emptyMessage?: string;
  children: (data: T) => ReactNode;
}

/**
 * The loading/error/empty/success rendering block every page in this app
 * repeats around a `useAsync` call. Extracted once the same four-way
 * conditional showed up independently in `DashboardPage`, `EvaluationPage`,
 * and `IncidentReportBrowser` -- real duplication, not a speculative
 * abstraction built ahead of need.
 */
export function AsyncSection<T>({
  state,
  errorTitle,
  loadingLabel,
  isEmpty,
  emptyMessage,
  children,
}: AsyncSectionProps<T>) {
  if (state.status === "loading") return <LoadingSpinner label={loadingLabel} />;
  if (state.status === "error") return <ErrorAlert title={errorTitle} message={state.error.message} />;
  if (isEmpty?.(state.data) && emptyMessage) return <EmptyState message={emptyMessage} />;
  return <>{children(state.data)}</>;
}

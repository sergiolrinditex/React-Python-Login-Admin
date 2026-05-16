/**
 * Hilo People — useDashboardUsage hook.
 *
 * Slice/Phase: P04-S01-T001 — AdminDashboardPage / Phase 4.
 * Write-set anchor: §D-T001-USEDASHBOARD
 *
 * Responsibility: TanStack Query useQuery wrapper around adminAiRepository.getUsage.
 *   Computes the default 30-day window client-side (D-T001-WINDOW-DEFAULT).
 *   Exposes isLoading, isError, isSuccess, data, error, refetch for the page.
 *
 * Clean Architecture: presentation/ layer — depends on data/adminAiRepository.
 *   Page mounts this hook; never calls the repository directly.
 *
 * TanStack Query v5 pattern (mirrors useHistory, useMe from P03 slices):
 *   queryKey: ["admin", "usage", "dashboard", { from, to, group_by }]
 *   staleTime: 30_000ms (30s) — dashboard data stales quickly during active sessions.
 *   gcTime: 300_000ms (5min) — consistent with chat pattern.
 *
 * Non-negotiables §logging: BEFORE + AFTER gated by VITE_ENABLE_VERBOSE_LOGGING.
 * PII-clean: logs only window dates, invocations count, error class name.
 */

import { useQuery } from "@tanstack/react-query";
import { useCallback, useMemo, useRef } from "react";
import { useAuth } from "../../auth/presentation/AuthProvider";
import { getUsage } from "../data/adminAiRepository";
import { AdminAiForbiddenError, AdminAiAuthExpiredError, type AdminAiError } from "../data/errors";
import type { UsageSummary } from "../domain/types";
import { logVerbose, logWarn, logError } from "../data/logger";

// ---------------------------------------------------------------------------
// Constants — D-T001-WINDOW-DEFAULT, D-T001-GROUPBY-DEFAULT
// ---------------------------------------------------------------------------

const WINDOW_DAYS = 30;
const DEFAULT_GROUP_BY = "model" as const;
const STALE_TIME_MS = 30_000;
const GC_TIME_MS = 300_000;

// ---------------------------------------------------------------------------
// Helper: compute default window
// ---------------------------------------------------------------------------

/**
 * Computes { from, to } as ISO-8601 strings for the last N days ending at `now`.
 * `now` is injectable for testing (defaults to Date.now()).
 *
 * @param nowMs - Current epoch timestamp in milliseconds.
 * @param days - Number of days to look back.
 * @returns { from, to } ISO-8601 UTC strings.
 */
export function computeUsageWindow(
  nowMs = Date.now(),
  days = WINDOW_DAYS,
): { from: string; to: string } {
  const to = new Date(nowMs);
  const from = new Date(nowMs - days * 24 * 60 * 60 * 1000);
  return {
    from: from.toISOString(),
    to: to.toISOString(),
  };
}

// ---------------------------------------------------------------------------
// Hook result type
// ---------------------------------------------------------------------------

export interface UseDashboardUsageResult {
  /** True while the first fetch is in-flight (loading skeleton). */
  isLoading: boolean;
  /** True if the query succeeded. */
  isSuccess: boolean;
  /** True if the query errored. */
  isError: boolean;
  /** Typed error from the last failed query. */
  error: AdminAiError | null;
  /** Usage summary data (defined when isSuccess). */
  data: UsageSummary | undefined;
  /** Trigger a manual refetch (used by retry CTA). */
  refetch: () => void;
  /** ISO-8601 from date for display. */
  from: string;
  /** ISO-8601 to date for display. */
  to: string;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Hook that wraps getUsage in a TanStack Query useQuery.
 * Computes the 30-day window at mount time (D-T001-WINDOW-DEFAULT).
 * Passes onAuthFailure from AuthProvider to handle final 401.
 *
 * @param nowMs - Injectable epoch timestamp for testing. Defaults to Date.now().
 * @returns UseDashboardUsageResult
 */
export function useDashboardUsage(nowMs?: number): UseDashboardUsageResult {
  const { logout } = useAuth();

  // Capture mount-time timestamp once. Using useRef prevents the window from
  // changing on re-renders, which would mutate the queryKey and cause an infinite
  // re-fetch loop. nowMs is injectable for tests; defaults to Date.now() at mount.
  const mountNowMs = useRef(nowMs ?? Date.now());

  // Compute the window at mount time only ([] dep array = computed once per mount).
  const { from, to } = useMemo(
    () => computeUsageWindow(mountNowMs.current),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const onAuthFailure = useCallback(() => {
    logWarn("admin-ai.hook.useDashboardUsage.auth_failure");
    void logout();
  }, [logout]);

  logVerbose("admin-ai.hook.useDashboardUsage.render", {
    from,
    to,
    group_by: DEFAULT_GROUP_BY,
  });

  const query = useQuery<UsageSummary, AdminAiError>({
    queryKey: ["admin", "usage", "dashboard", { from, to, group_by: DEFAULT_GROUP_BY }],
    queryFn: async () => {
      logVerbose("admin-ai.hook.useDashboardUsage.queryFn.start", {
        from,
        to,
        group_by: DEFAULT_GROUP_BY,
      });

      const result = await getUsage(
        { from, to, group_by: DEFAULT_GROUP_BY },
        onAuthFailure,
      );

      if (!result.ok) {
        logError("admin-ai.hook.useDashboardUsage.queryFn.error", {
          error_class: result.error.constructor.name,
        });
        throw result.error;
      }

      logVerbose("admin-ai.hook.useDashboardUsage.queryFn.ok", {
        row_count: result.value.rows.length,
        total_invocations: result.value.totals.invocations,
      });

      return result.value;
    },
    staleTime: STALE_TIME_MS,
    gcTime: GC_TIME_MS,
    retry: false,
  });

  // Map TanStack error to AdminAiError — query.error is unknown but we throw typed errors.
  const typedError: AdminAiError | null = query.error instanceof Error
    ? (query.error as AdminAiError)
    : query.error !== null
      ? null
      : null;

  // Auth expiry from query error — call onAuthFailure once if needed (belt-and-suspenders).
  if (typedError instanceof AdminAiAuthExpiredError) {
    logWarn("admin-ai.hook.useDashboardUsage.auth_expired_in_error");
  }
  if (typedError instanceof AdminAiForbiddenError) {
    logWarn("admin-ai.hook.useDashboardUsage.forbidden_in_error");
  }

  return {
    isLoading: query.isLoading,
    isSuccess: query.isSuccess,
    isError: query.isError,
    error: typedError,
    data: query.data,
    refetch: () => {
      logVerbose("admin-ai.hook.useDashboardUsage.refetch");
      void query.refetch();
    },
    from,
    to,
  };
}

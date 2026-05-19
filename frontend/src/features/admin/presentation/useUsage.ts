/**
 * Hilo People — useUsage presentation hook.
 *
 * Slice/Phase: P04-S03-T002 — UsagePage / Phase 4 Complete Features.
 *
 * Responsibility: TanStack Query v5 useQuery wrapper around getUsage.
 *   This is the FIRST useQuery hook in the project (previous hooks used useMutation).
 *   Documents the canonical v5 useQuery pattern for downstream slices.
 *
 * TanStack Query v5 useQuery pattern (canonical — no onError/onSuccess in options):
 *   const { data, error, isPending, isFetching, refetch } = useQuery({
 *     queryKey: ["admin","usage",{from,to,groupBy}],
 *     queryFn: async ({signal}) => { ... },
 *     staleTime: 30_000,
 *     retry: 1,
 *     enabled: rangeIsValid,
 *   });
 *
 * Decisions applied:
 *   D-T002-USEUSAGE: This file is the canonical anchor.
 *   D-T002-QUERY-KEY: ["admin","usage",{from,to,groupBy}]
 *   D-T002-ABORT-CONTROLLER: signal from queryFn passed to getUsage.
 *   D-T002-STALE-TIME: staleTime 30s (usage is read-only aggregated data).
 *   D-T002-RETRY: retry:1 (aligns with project QueryClient default).
 *   D-T002-RANGE-INVARIANT: enabled=false when range is invalid (no fetch).
 *   D-T002-LANGUAGE-SOURCE: i18n.language passed via Intl.NumberFormat in UsagePage.
 *
 * Clean Architecture: presentation/ layer — depends on data/usageRepository.ts.
 *   QueryClientProvider is mounted above this hook (app/providers.tsx).
 *
 * Security: onAuthFailure wired from useAuth().logout — no direct navigation here.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR gated by VITE_ENABLE_VERBOSE_LOGGING.
 *
 * D-T002-USEUSAGE: Canonical write_set anchor for this file.
 * Source ref: §D-T002-USEUSAGE, task pack §4 Architectural patterns.
 */

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../auth/presentation/AuthProvider";
import { getUsage } from "../data/usageRepository";
import { logVerbose, logError } from "../data/logger";
import type { UsageSummary, UsageQuery } from "../domain/types";
import type { UsageError } from "../data/errors";
import type { Result } from "../../auth/domain/AuthRepository";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Maximum window in days (mirrors backend _MAX_WINDOW_DAYS = 90). */
const MAX_WINDOW_DAYS = 90;

/** Stale time: usage is aggregated read-only data; 30s window avoids re-fetching. */
const STALE_TIME_MS = 30_000;

/** GC time: keep cached results for 5 minutes after component unmounts. */
const GC_TIME_MS = 5 * 60 * 1_000;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Props for useUsage — the query parameters for the usage endpoint. */
export interface UseUsageProps {
  from: Date;
  to: Date;
  groupBy: UsageQuery["groupBy"];
}

/** Return type from useUsage hook. */
export interface UseUsageResult {
  /** Resolved usage summary (present on success). */
  data: UsageSummary | undefined;
  /** Typed error from last failed query attempt. */
  error: UsageError | null;
  /** True while initial fetch is in-flight (no data yet). */
  isPending: boolean;
  /** True while any background refetch is in-flight. */
  isFetching: boolean;
  /** Trigger a manual refetch (e.g., on retry CTA click). */
  refetch: () => void;
  /** True when client-side range invariant fails (D-T002-RANGE-INVARIANT). */
  isRangeInvalid: boolean;
}

// ---------------------------------------------------------------------------
// Range validation (D-T002-RANGE-INVARIANT)
// ---------------------------------------------------------------------------

/**
 * Validates the query range client-side before fetching.
 * Prevents avoidable 422 round-trips to the backend.
 *
 * Rules (mirrors backend validation):
 *   - to > from (strict)
 *   - (to - from) <= 90 days
 *
 * @param from - Window start date.
 * @param to - Window end date.
 * @returns True if the range is valid for fetching.
 */
export function isRangeValid(from: Date, to: Date): boolean {
  const diffMs = to.getTime() - from.getTime();
  const diffDays = diffMs / 86_400_000;
  return diffMs > 0 && diffDays <= MAX_WINDOW_DAYS;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * TanStack Query v5 useQuery hook for admin usage data.
 *
 * Usage:
 *   const { data, error, isPending, refetch } = useUsage({ from, to, groupBy });
 *
 * Key: ["admin","usage",{from,to,groupBy}] — invalidates when params change.
 * Enabled: only when isRangeValid(from, to) — D-T002-RANGE-INVARIANT.
 * AbortController: queryFn receives signal from TanStack; passed to getUsage.
 *
 * @param props - Query parameters (from, to, groupBy).
 * @returns UseUsageResult with data, error, loading states, and refetch.
 */
export function useUsage({ from, to, groupBy }: UseUsageProps): UseUsageResult {
  const { logout } = useAuth();
  const rangeValid = isRangeValid(from, to);

  logVerbose("usage.hook.useUsage.render", {
    from: from.toISOString(),
    to: to.toISOString(),
    group_by: groupBy,
    range_valid: rangeValid,
  });

  const query = useQuery<Result<UsageSummary, UsageError>, UsageError>({
    queryKey: ["admin", "usage", { from: from.toISOString(), to: to.toISOString(), groupBy }],
    queryFn: async ({ signal }) => {
      logVerbose("usage.hook.queryFn.start", {
        from: from.toISOString(),
        to: to.toISOString(),
        group_by: groupBy,
      });

      const result = await getUsage(
        { from, to, groupBy },
        () => void logout(),
        signal,
      );

      if (!result.ok) {
        logError("usage.hook.queryFn.error", { error_code: result.error.code });
        throw result.error;
      }

      logVerbose("usage.hook.queryFn.ok", {
        row_count: result.value.rows.length,
      });

      return result;
    },
    staleTime: STALE_TIME_MS,
    gcTime: GC_TIME_MS,
    retry: 1,
    enabled: rangeValid,
  });

  // Unwrap Result from queryData (queryFn resolves to Result, throws on error)
  const usageSummary = query.data?.ok ? query.data.value : undefined;

  // Cast error from the query (TanStack stores thrown value as error)
  const typedError = query.error as UsageError | null;

  return {
    data: usageSummary,
    error: typedError,
    isPending: query.isPending && rangeValid,
    isFetching: query.isFetching,
    refetch: () => {
      logVerbose("usage.hook.refetch.triggered");
      void query.refetch();
    },
    isRangeInvalid: !rangeValid,
  };
}

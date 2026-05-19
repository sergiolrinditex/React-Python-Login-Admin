/**
 * Hilo People — useAuditQuery presentation hook.
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: TanStack Query v5 useQuery wrapper around getAuditPage.
 *   Manages the audit log query lifecycle: loading, success, error, pagination.
 *   Mirrors the useUsage pattern from features/admin/presentation/useUsage.ts.
 *
 * TanStack Query v5 useQuery pattern (canonical — no onError/onSuccess in options):
 *   const { data, error, isPending, isFetching, refetch } = useQuery({
 *     queryKey: ["admin","audit",{...params}],
 *     queryFn: async ({signal}) => { ... },
 *     staleTime: 30_000,
 *     retry: 1,
 *     enabled: rangeIsValid,
 *   });
 *
 * Decisions applied:
 *   D-T001-PRESENTATION: This file is the canonical anchor.
 *   D-T001-QUERY-KEY: ["admin","audit",{from,to,actor,action,cursor,limit}]
 *   D-T001-ABORT-CONTROLLER: signal from queryFn passed to getAuditPage.
 *   D-T001-STALE-TIME: staleTime 30s (audit logs are read-only).
 *   D-T001-RETRY: retry:1 (aligns with project QueryClient default).
 *   D-T001-RANGE-INVARIANT: enabled=false when range is invalid (no fetch).
 *   D-T001-PAGINATION: load-more via cursor; appends rows to existing state.
 *
 * Clean Architecture: presentation/ layer — depends on data/auditRepository.ts.
 *   QueryClientProvider is mounted above this hook (app/providers.tsx).
 *
 * Security: onAuthFailure wired from useAuth().logout — no direct navigation here.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR gated by VITE_ENABLE_VERBOSE_LOGGING.
 *
 * §D-T001-PRESENTATION: Canonical write_set anchor for this file.
 * Source ref: §D-T001-PRESENTATION, task pack §4 Architectural patterns.
 */

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../auth/presentation/AuthProvider";
import { getAuditPage } from "../data/auditRepository";
import { logVerbose, logError } from "../data/logger";
import { AUDIT_MAX_WINDOW_DAYS } from "../domain/types";
import type { AuditQuery, AuditPage } from "../domain/types";
import type { AuditError } from "../data/errors";
import type { Result } from "../../auth/domain/AuthRepository";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Stale time: audit logs are read-only data; 30s window avoids re-fetching. */
const STALE_TIME_MS = 30_000;

/** GC time: keep cached results for 5 minutes after component unmounts. */
const GC_TIME_MS = 5 * 60 * 1_000;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Props for useAuditQuery — the query parameters for the audit endpoint. */
export interface UseAuditQueryProps {
  from: Date;
  to: Date;
  actor?: string;
  action?: string;
  cursor?: string;
  limit?: number;
}

/** Return type from useAuditQuery hook. */
export interface UseAuditQueryResult {
  /** Resolved audit page (present on success). */
  data: AuditPage | undefined;
  /** Typed error from last failed query attempt. */
  error: AuditError | null;
  /** True while initial fetch is in-flight (no data yet). */
  isPending: boolean;
  /** True while any background refetch is in-flight. */
  isFetching: boolean;
  /** Trigger a manual refetch (e.g., on retry CTA click). */
  refetch: () => void;
  /** True when client-side range invariant fails (D-T001-RANGE-INVARIANT). */
  isRangeInvalid: boolean;
  /** True when actor string is not a valid UUID format. */
  isActorInvalid: boolean;
}

// ---------------------------------------------------------------------------
// Validation helpers (D-T001-RANGE-INVARIANT)
// ---------------------------------------------------------------------------

/**
 * UUID v4 regex for client-side actor validation.
 * Server does UUID validation; client mirrors for UX (no avoidable 422).
 */
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Validates the query range client-side before fetching.
 * Prevents avoidable 422 round-trips to the backend.
 *
 * Rules (mirrors backend validation):
 *   - to > from (strict)
 *   - (to - from) <= AUDIT_MAX_WINDOW_DAYS days
 *
 * @param from - Window start date.
 * @param to - Window end date.
 * @returns True if the range is valid for fetching.
 */
export function isAuditRangeValid(from: Date, to: Date): boolean {
  const diffMs = to.getTime() - from.getTime();
  const diffDays = diffMs / 86_400_000;
  return diffMs > 0 && diffDays <= AUDIT_MAX_WINDOW_DAYS;
}

/**
 * Validates the actor UUID string (optional field).
 * Returns true when actor is empty/undefined OR is a valid UUID.
 *
 * @param actor - Optional actor UUID string.
 * @returns True when actor is absent or valid.
 */
export function isActorValid(actor?: string): boolean {
  if (!actor || actor.trim() === "") return true;
  return UUID_REGEX.test(actor.trim());
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * TanStack Query v5 useQuery hook for admin audit log data.
 *
 * Usage:
 *   const { data, error, isPending, refetch } = useAuditQuery({ from, to, actor, action });
 *
 * Key: ["admin","audit",{from,to,actor,action,cursor,limit}]
 * Enabled: only when range and actor are valid — D-T001-RANGE-INVARIANT.
 * AbortController: queryFn receives signal from TanStack; passed to getAuditPage.
 *
 * @param props - Query parameters (from, to, optional actor/action/cursor/limit).
 * @returns UseAuditQueryResult with data, error, loading states, and refetch.
 */
export function useAuditQuery({
  from,
  to,
  actor,
  action,
  cursor,
  limit,
}: UseAuditQueryProps): UseAuditQueryResult {
  const { logout } = useAuth();
  const rangeValid = isAuditRangeValid(from, to);
  const actorValid = isActorValid(actor);
  const canFetch = rangeValid && actorValid;

  logVerbose("audit.hook.useAuditQuery.render", {
    has_from: true,
    has_to: true,
    action_present: action !== undefined,
    actor_present: actor !== undefined,
    range_valid: rangeValid,
    actor_valid: actorValid,
  });

  const query = useQuery<Result<AuditPage, AuditError>, AuditError>({
    queryKey: [
      "admin",
      "audit",
      {
        from: from.toISOString(),
        to: to.toISOString(),
        actor: actor ?? null,
        action: action ?? null,
        cursor: cursor ?? null,
        limit: limit ?? 50,
      },
    ],
    queryFn: async ({ signal }) => {
      logVerbose("audit.hook.queryFn.start", {
        has_from: true,
        has_to: true,
        action_present: action !== undefined,
        actor_present: actor !== undefined,
      });

      const queryParams: AuditQuery = { from, to };
      if (actor && actor.trim()) queryParams.actor = actor.trim();
      if (action && action.trim()) queryParams.action = action.trim();
      if (cursor) queryParams.cursor = cursor;
      if (limit !== undefined) queryParams.limit = limit;

      const result = await getAuditPage(
        queryParams,
        () => void logout(),
        signal,
      );

      if (!result.ok) {
        logError("audit.hook.queryFn.error", { error_code: result.error.code });
        throw result.error;
      }

      logVerbose("audit.hook.queryFn.ok", {
        count: result.value.count,
        has_more: result.value.has_more,
      });

      return result;
    },
    staleTime: STALE_TIME_MS,
    gcTime: GC_TIME_MS,
    retry: 1,
    enabled: canFetch,
  });

  // Unwrap Result from queryData (queryFn resolves to Result, throws on error)
  const auditPage = query.data?.ok ? query.data.value : undefined;

  // Cast error from the query (TanStack stores thrown value as error)
  const typedError = query.error as AuditError | null;

  return {
    data: auditPage,
    error: typedError,
    isPending: query.isPending && canFetch,
    isFetching: query.isFetching,
    refetch: () => {
      logVerbose("audit.hook.refetch.triggered");
      void query.refetch();
    },
    isRangeInvalid: !rangeValid,
    isActorInvalid: !actorValid,
  };
}

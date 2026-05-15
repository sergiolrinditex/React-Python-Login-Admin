/**
 * Hilo People — useHistory hook.
 *
 * Slice/Phase: P03-S02-T003 — HistoryPage / Phase 3.
 *
 * Responsibility: TanStack Query v5 useQuery wrapper around chatRepository.listConversations.
 *   Returns the paginated first page of conversations for the authenticated employee.
 *
 * §D-T003-USEHISTORY — query key ["chat","history"], staleTime 30s, gcTime 5min.
 * Mirrors useConversation (T002) and useMe (T004) patterns.
 *
 * Clean Architecture: presentation/ layer — depends on data/chatRepository.
 *   HistoryPage depends on this hook; no direct repository imports in the page.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR via logVerbose/logWarn.
 * Logging: PII-clean — no IDs, no titles, only count + has_more.
 *
 * Key deps: @tanstack/react-query v5 (useQuery), chatRepository.listConversations.
 */

import { useQuery } from "@tanstack/react-query";
import type { ListConversationsResponse } from "../domain/types";
import type { ChatError } from "../data/errors";
import { listConversations } from "../data/chatRepository";
import { logVerbose, logWarn } from "../data/logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const HISTORY_QUERY_KEY = ["chat", "history"] as const;
const STALE_TIME = 30_000;         // 30 seconds
const GC_TIME = 5 * 60_000;       // 5 minutes

// ---------------------------------------------------------------------------
// Public hook
// ---------------------------------------------------------------------------

/**
 * Fetches the first page of conversations for the current authenticated employee.
 *
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns TanStack useQuery result with ListConversationsResponse as data type.
 */
export function useHistory(onAuthFailure: () => void) {
  return useQuery<ListConversationsResponse, ChatError>({
    queryKey: HISTORY_QUERY_KEY,
    queryFn: async ({ signal }) => {
      logVerbose("chat.useHistory.fetch.start", {});

      const result = await listConversations(
        { signal },
        onAuthFailure,
      );

      if (!result.ok) {
        logWarn("chat.useHistory.fetch.error", { code: result.error.code });
        throw result.error;
      }

      logVerbose("chat.useHistory.fetch.success", {
        count: result.value.data.length,
        has_more: result.value.meta.pagination?.has_more ?? false,
      });

      return result.value;
    },
    staleTime: STALE_TIME,
    gcTime: GC_TIME,
    // retry controlled by QueryClient defaultOptions in tests (default 3 retries in prod).
  });
}

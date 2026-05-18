/**
 * Hilo People — useConversation hook (§D-T002-USECONV).
 *
 * Slice/Phase: P03-S02-T008 — ConversationPage re-implementation / Phase 3.
 *   Re-implemented from reference branch f7f5f33 (P03-S02-T002).
 *
 * Responsibility: TanStack Query useQuery wrapper for GET /api/v1/chat/conversations/{id}.
 *   Returns the full ConversationDetail (transcript + citations) for the given id.
 *   Disabled automatically when id is falsy (e.g. on initial mount before route param is available).
 *
 * Cache strategy (§D-T002-USECONV):
 *   - staleTime: 30s — transcript rarely changes between renders.
 *   - gcTime: 5min — keep in memory for back-navigation.
 *   - refetchOnWindowFocus: false — streaming updates are pushed via setQueryData,
 *     not background refetches (§D-T002-TANSTACK-CACHE).
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR on query lifecycle.
 * Logging rules: NO message content, NO citation snippets (§D-T002-NO-PII-IN-LOGS).
 *
 * Key deps: @tanstack/react-query v5, features/chat/data/chatRepository.getConversation.
 */

import { useQuery } from "@tanstack/react-query";
import type { ConversationDetail } from "../domain/types";
import type { ChatError } from "../data/errors";
import { getConversation } from "../data/chatRepository";
import { logVerbose, logError } from "../data/logger";

// ---------------------------------------------------------------------------
// Query key factory (exported for use in setQueryData)
// ---------------------------------------------------------------------------

/** Stable query key for a conversation detail. */
export const conversationQueryKey = (id: string): ["conversation", string] => [
  "conversation",
  id,
];

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface UseConversationResult {
  /** The full conversation detail including messages and citations. */
  data: ConversationDetail | undefined;
  /** Query status: 'pending' | 'error' | 'success'. */
  status: "pending" | "error" | "success";
  /** Typed error on failure, null otherwise. */
  error: ChatError | null;
  /** True while the first fetch is in flight. */
  isLoading: boolean;
  /** True when data is available (even if stale). */
  isSuccess: boolean;
  /** Manually trigger a refetch. */
  refetch: () => void;
}

/**
 * Fetches and caches a conversation detail for the given id.
 *
 * @param id - Conversation UUID. Pass empty string or undefined to disable.
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns UseConversationResult
 */
export function useConversation(
  id: string | undefined,
  onAuthFailure: () => void,
): UseConversationResult {
  const enabled = Boolean(id);

  const query = useQuery<ConversationDetail, ChatError>({
    queryKey: conversationQueryKey(id ?? ""),
    queryFn: async () => {
      logVerbose("chat.hook.useConversation.fetch.start", {
        conversation_id: id?.slice(0, 8),
      });

      const result = await getConversation(id!, onAuthFailure);

      if (!result.ok) {
        logError("chat.hook.useConversation.fetch.error", {
          error: result.error.code,
          conversation_id: id?.slice(0, 8),
        });
        throw result.error;
      }

      logVerbose("chat.hook.useConversation.fetch.ok", {
        conversation_id: result.value.id.slice(0, 8),
        message_count: result.value.messages.length,
        citation_count: result.value.citations.length,
      });

      return result.value;
    },
    enabled,
    staleTime: 30_000,   // 30s
    gcTime: 5 * 60_000,  // 5min
    refetchOnWindowFocus: false,
    retry: false,         // Retry is manual via retry CTA (§D-T002-RETRY-SAME-PROMPT)
  });

  return {
    data: query.data,
    status: query.status,
    error: query.error ?? null,
    isLoading: query.isLoading,
    isSuccess: query.isSuccess,
    refetch: () => { void query.refetch(); },
  };
}

/**
 * Hilo People — useCreateConversation hook.
 *
 * Slice/Phase: P03-S02-T001 — ChatHomePage / Phase 3.
 *
 * Responsibility: TanStack Query useMutation wrapper around chatRepository.createConversation.
 *   Follows D-T001-TANSTACK-MUTATION decision: uses useMutation from @tanstack/react-query.
 *   QueryClientProvider is already mounted above this hook (providers.tsx).
 *
 * Clean Architecture: presentation/ layer — depends on data/chatRepository.
 *   Presentation decides navigation; repository handles HTTP.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR on mutation lifecycle.
 */

import { useMutation } from "@tanstack/react-query";
import type { CreateConversationRequest, Conversation } from "../domain/types";
import type { ChatError } from "../data/errors";
import { createConversation } from "../data/chatRepository";
import { logVerbose, logError } from "../data/logger";

// ---------------------------------------------------------------------------
// Hook result type
// ---------------------------------------------------------------------------

export interface UseCreateConversationResult {
  /** Call to trigger POST /api/v1/chat/conversations. */
  mutate: (
    request: CreateConversationRequest,
    options?: { onSuccess?: (data: Conversation) => void; onError?: (err: ChatError) => void },
  ) => void;
  /** True while the mutation is in-flight. */
  isPending: boolean;
  /** Typed error from the last failed mutation attempt. */
  error: ChatError | null;
  /** Result from last successful mutation. */
  data: Conversation | undefined;
  /** Reset mutation state (clear error + data). */
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Hook that wraps createConversation in a TanStack Query mutation.
 *
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 *   Typically wired from useAuth().logout or RequireAuth redirect logic.
 * @returns UseCreateConversationResult
 */
export function useCreateConversation(
  onAuthFailure: () => void,
): UseCreateConversationResult {
  const mutation = useMutation<
    Conversation,
    ChatError,
    CreateConversationRequest
  >({
    mutationFn: async (request: CreateConversationRequest) => {
      logVerbose("chat.hook.useCreateConversation.mutate.start", {
        prompt_len: request.initial_message?.length ?? 0,
        language: request.language ?? "default",
      });

      const result = await createConversation(request, onAuthFailure);

      if (!result.ok) {
        logError("chat.hook.useCreateConversation.mutate.error", {
          error: result.error.code,
        });
        throw result.error;
      }

      logVerbose("chat.hook.useCreateConversation.mutate.ok", {
        conversation_id: result.value.conversation_id,
      });

      return result.value;
    },
  });

  return {
    mutate: (request, options) => {
      mutation.mutate(request, {
        onSuccess: options?.onSuccess,
        onError: options?.onError,
      });
    },
    isPending: mutation.isPending,
    error: mutation.error ?? null,
    data: mutation.data,
    reset: mutation.reset,
  };
}

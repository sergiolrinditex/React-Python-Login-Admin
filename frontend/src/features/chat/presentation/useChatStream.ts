/**
 * Hilo People — useChatStream hook (§D-T002-USESTREAM).
 *
 * Slice/Phase: P03-S02-T002 — ConversationPage / Phase 3.
 *
 * Responsibility: React state machine that owns the streaming lifecycle.
 *   Wraps streamConversation from features/chat/stream.ts.
 *   Owns an AbortController; aborts on unmount and on conversationId change (§D-T002-ABORT-ON-UNMOUNT).
 *   On `done` event, writes the complete assistant message + citations into TanStack
 *   Query cache via setQueryData so back-nav does NOT trigger a refetch (§D-T002-TANSTACK-CACHE).
 *
 * State machine phases:
 *   idle → streaming → completed | error_network | error_validation | error_stream
 *   Any error → idle via retry()
 *
 * Logging: BEFORE/AFTER/ERROR gated by VITE_ENABLE_VERBOSE_LOGGING (§D-T002-NO-PII-IN-LOGS).
 *   NEVER log assistantText (delta content), citation snippets, or prompt text.
 *
 * Key deps: @tanstack/react-query v5 (useQueryClient), features/chat/stream (streamConversation).
 */

import {
  useState,
  useRef,
  useCallback,
  useEffect,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { SseCitationEvent } from "../domain/types";
import type { ConversationDetail, Message, MessageCitation } from "../domain/types";
import type { ChatError } from "../data/errors";
import { streamConversation } from "../stream";
import { conversationQueryKey } from "./useConversation";
import { logVerbose, logWarn, logError } from "../data/logger";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** All possible streaming phases. */
export type StreamPhase =
  | "idle"
  | "streaming"
  | "completed"
  | "error_network"
  | "error_validation"
  | "permission_denied"
  | "not_found"
  | "auth_expired"
  | "error_stream";

export interface UseChatStreamResult {
  /** Current streaming phase. */
  phase: StreamPhase;
  /** Accumulated assistant text during streaming (grows chunk by chunk). */
  assistantText: string;
  /** Citations received during this stream (ordered by arrival — see §D-T002-CITATIONS-INLINE). */
  citations: SseCitationEvent["payload"][];
  /** Last error for rendering error states. */
  lastError: ChatError | undefined;
  /** Start a new streaming request with the given message. */
  start: (message: string) => void;
  /** Retry the last failed request with the same message. */
  retry: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Controls the streaming lifecycle for a conversation turn.
 *
 * @param conversationId - Conversation UUID (route param).
 * @param onAuthFailure - Called when session expires; triggers logout/redirect.
 * @returns UseChatStreamResult
 */
export function useChatStream(
  conversationId: string,
  onAuthFailure: () => void,
): UseChatStreamResult {
  const queryClient = useQueryClient();

  const [phase, setPhase] = useState<StreamPhase>("idle");
  const [assistantText, setAssistantText] = useState("");
  const [citations, setCitations] = useState<SseCitationEvent["payload"][]>([]);
  const [lastError, setLastError] = useState<ChatError | undefined>(undefined);

  // Refs hold mutable state that must not cause re-renders
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastPromptRef = useRef<string>("");
  // Track message_id from meta event to build the cache entry
  const metaMessageIdRef = useRef<string | null>(null);

  // ---------------------------------------------------------------------------
  // Cleanup on unmount or conversationId change (§D-T002-ABORT-ON-UNMOUNT)
  // ---------------------------------------------------------------------------
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        logVerbose("chat.useChatStream.unmount_abort", {
          conversation_id: conversationId,
        });
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    };
  }, [conversationId]);

  // ---------------------------------------------------------------------------
  // start
  // ---------------------------------------------------------------------------
  const start = useCallback(
    (message: string): void => {
      // Abort any in-flight stream
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();
      lastPromptRef.current = message;
      metaMessageIdRef.current = null;

      // Reset streaming state
      setPhase("streaming");
      setAssistantText("");
      setCitations([]);
      setLastError(undefined);

      logVerbose("chat.useChatStream.start", {
        conversation_id: conversationId,
        message_len: message.length,
      });

      // Local accumulator refs to build the cache entry atomically on done
      let localText = "";
      const localCitations: SseCitationEvent["payload"][] = [];

      void streamConversation(
        conversationId,
        message,
        {
          onMeta: (payload) => {
            metaMessageIdRef.current = payload.message_id;
            logVerbose("chat.useChatStream.meta", {
              conversation_id: conversationId,
              message_id: payload.message_id,
            });
          },
          onChunk: (payload) => {
            // Accumulate in local ref (no PII log — §D-T002-NO-PII-IN-LOGS)
            localText += payload.delta;
            setAssistantText((prev) => prev + payload.delta);
          },
          onCitation: (payload) => {
            localCitations.push(payload);
            setCitations((prev) => [...prev, payload]);
            logVerbose("chat.useChatStream.citation", {
              conversation_id: conversationId,
              document_id: payload.document_id,
              score: payload.score,
            });
          },
          onUsage: (payload) => {
            logVerbose("chat.useChatStream.usage", {
              conversation_id: conversationId,
              tokens_in: payload.tokens_in,
              tokens_out: payload.tokens_out,
            });
          },
          onError: (payload) => {
            logError("chat.useChatStream.server_error_event", {
              conversation_id: conversationId,
              code: payload.code,
            });
            // Phase transition handled in the result below
          },
          onDone: (payload) => {
            logVerbose("chat.useChatStream.done", {
              conversation_id: conversationId,
              message_id: payload.message_id,
            });

            // Write into TanStack cache (§D-T002-TANSTACK-CACHE):
            // Append the assistant message + its citations to the cached ConversationDetail.
            queryClient.setQueryData<ConversationDetail>(
              conversationQueryKey(conversationId),
              (old) => {
                if (!old) return old;

                const msgId = payload.message_id;
                const now = new Date().toISOString();

                const newMessage: Message = {
                  id: msgId,
                  conversation_id: conversationId,
                  role: "assistant",
                  content: localText,
                  token_count: null,
                  created_at: now,
                };

                const newCitations: MessageCitation[] = localCitations.map(
                  (c, idx) => ({
                    id: `${msgId}-cit-${idx}`,
                    message_id: msgId,
                    document_id: c.document_id,
                    chunk_id: c.chunk_id,
                    label: c.label,
                    score: c.score,
                  }),
                );

                return {
                  ...old,
                  messages: [...old.messages, newMessage],
                  citations: [...old.citations, ...newCitations],
                };
              },
            );

            setPhase("completed");
          },
        },
        {
          signal: abortControllerRef.current.signal,
          onAuthFailure,
        },
      ).then((result) => {
        if (result.ok) {
          // Normal completion or abort — phase already set by onDone or left as-is
          logVerbose("chat.useChatStream.result.ok", {
            conversation_id: conversationId,
          });
        } else {
          const err = result.error;
          logError("chat.useChatStream.result.error", {
            conversation_id: conversationId,
            error: err.code,
          });
          setLastError(err);

          // Map error code to phase
          if (err.code === "CHAT_FORBIDDEN") {
            setPhase("permission_denied");
          } else if (err.code === "CHAT_NOT_FOUND") {
            setPhase("not_found");
          } else if (err.code === "CHAT_AUTH_EXPIRED") {
            setPhase("auth_expired");
          } else if (err.code === "CHAT_VALIDATION_ERROR") {
            setPhase("error_validation");
          } else if (err.code === "CHAT_STREAM_ERROR") {
            setPhase("error_stream");
          } else {
            setPhase("error_network");
          }
        }
      }).catch((err: unknown) => {
        // Unexpected rejection (should not happen — streamConversation always returns Result)
        logError("chat.useChatStream.unexpected_rejection", {
          conversation_id: conversationId,
          error: String(err),
        });
        setPhase("error_network");
      });
    },
    [conversationId, onAuthFailure, queryClient],
  );

  // ---------------------------------------------------------------------------
  // retry — §D-T002-RETRY-SAME-PROMPT
  // ---------------------------------------------------------------------------
  const retry = useCallback((): void => {
    const lastPrompt = lastPromptRef.current;
    if (!lastPrompt) {
      logWarn("chat.useChatStream.retry.no_prompt", { conversation_id: conversationId });
      return;
    }
    logVerbose("chat.useChatStream.retry", {
      conversation_id: conversationId,
      message_len: lastPrompt.length,
    });
    start(lastPrompt);
  }, [start, conversationId]);

  return {
    phase,
    assistantText,
    citations,
    lastError,
    start,
    retry,
  };
}

/**
 * Hilo People — Chat SSE streaming client (§D-T002-STREAM-MODULE).
 *
 * Slice/Phase: P03-S02-T008 — ConversationPage re-implementation / Phase 3.
 *   Re-implemented from reference branch f7f5f33 (P03-S02-T002).
 *
 * Responsibility: Pure SSE parser + streaming HTTP client for chat.
 *   Parses the 6-event wire format from POST /api/v1/chat/conversations/{id}/stream.
 *   Uses authFetch + ReadableStream + TextDecoder — NOT EventSource (§D-T002-NO-EVENTSOURCE).
 *   Exposes a callback-based API via streamConversation(); the pure inner parser
 *   (_parseSseRecord) is separately testable with fixture strings.
 *
 * §D-T002-STREAM-API decision: callback-based (StreamHandlers) rather than async iterator.
 *   Rationale: avoids generator-consumer timing complexity in React; handlers fire
 *   synchronously in the read loop, letting useChatStream setState in a predictable order.
 *
 * SSE wire format (W3C text/event-stream, per backend app/chat/streaming/sse.py):
 *   event: <name>\n
 *   data: <json-payload>\n
 *   \n
 *
 * Event order in V1 (confirmed from service.py run_stream):
 *   meta → citation* → chunk* → usage → done | error
 *
 * Security / logging:
 *   - NEVER log delta text, citation snippets, or message content (§D-T002-NO-PII-IN-LOGS).
 *   - Log conversation_id prefix, event counts, request_id, status codes only.
 *   - Verbose flag: VITE_ENABLE_VERBOSE_LOGGING.
 *
 * Key deps: authFetch from features/auth/data/httpClient (read-only), chat errors/logger.
 */

import type { Result } from "../auth/domain/AuthRepository";
import type {
  SseEvent,
  SseMetaEvent,
  SseChunkEvent,
  SseCitationEvent,
  SseUsageEvent,
  SseErrorEvent,
  SseDoneEvent,
} from "./domain/types";
import { authFetch } from "../auth/data/httpClient";
import {
  ChatValidationError,
  ChatAuthExpiredError,
  ChatForbiddenError,
  ChatNotFoundError,
  ChatStreamError,
  ChatServerError,
  ChatNetworkError,
  mapChatError,
  type ChatError,
} from "./data/errors";
import { logVerbose, logWarn, logError } from "./data/logger";

// ---------------------------------------------------------------------------
// Public interface
// ---------------------------------------------------------------------------

/**
 * Handlers fired as SSE events arrive from the stream.
 * Each handler is called synchronously in the read loop.
 * §D-T002-NO-PII-IN-LOGS applies: handlers must not log payload content.
 */
export interface StreamHandlers {
  onMeta(event: SseMetaEvent["payload"]): void;
  onChunk(event: SseChunkEvent["payload"]): void;
  onCitation(event: SseCitationEvent["payload"]): void;
  onUsage(event: SseUsageEvent["payload"]): void;
  onError(event: SseErrorEvent["payload"]): void;
  onDone(event: SseDoneEvent["payload"]): void;
}

export interface StreamOptions {
  /** AbortSignal — caller provides; abort() cancels the stream cleanly. */
  signal: AbortSignal;
  /** Called when 401 persists after single-flight refresh. */
  onAuthFailure: () => void;
}

// ---------------------------------------------------------------------------
// Internal: SSE buffer parser (§D-T002-SSE-PARSE)
// Pure function — testable without network.
// ---------------------------------------------------------------------------

/**
 * Parses one complete SSE record (lines between double-newlines).
 * Returns a typed SseEvent or null if the record is empty/malformed.
 *
 * @param record - Raw SSE record text (without the trailing \n\n).
 * @returns Typed SseEvent or null on parse failure.
 */
export function _parseSseRecord(record: string): SseEvent | null {
  if (!record.trim()) return null;

  const lines = record.split("\n");
  let eventName = "";
  let dataLine = "";

  for (const line of lines) {
    if (line.startsWith("event: ")) {
      eventName = line.slice("event: ".length).trim();
    } else if (line.startsWith("data: ")) {
      dataLine = line.slice("data: ".length).trim();
    }
  }

  if (!eventName || !dataLine) return null;

  let payload: unknown;
  try {
    payload = JSON.parse(dataLine);
  } catch {
    logWarn("chat.stream.parse.malformed_json", { event: eventName });
    return null;
  }

  switch (eventName) {
    case "meta":
      return { kind: "meta", payload } as SseMetaEvent;
    case "chunk":
      return { kind: "chunk", payload } as SseChunkEvent;
    case "citation":
      return { kind: "citation", payload } as SseCitationEvent;
    case "usage":
      return { kind: "usage", payload } as SseUsageEvent;
    case "error":
      return { kind: "error", payload } as SseErrorEvent;
    case "done":
      return { kind: "done", payload } as SseDoneEvent;
    default:
      // Unknown event name — log and skip (forward-compat)
      logWarn("chat.stream.parse.unknown_event", { event: eventName });
      return null;
  }
}

// ---------------------------------------------------------------------------
// Public: streamConversation
// ---------------------------------------------------------------------------

/**
 * Opens POST /api/v1/chat/conversations/{id}/stream and fires handlers for each SSE event.
 *
 * Algorithm (§D-T002-SSE-PARSE):
 *   1. POST via authFetch (inherits auth + X-Request-ID + single-flight 401 refresh).
 *   2. On non-200 HTTP → map to typed ChatError, return Result.err.
 *   3. On 200 → read ReadableStream<Uint8Array> via getReader().
 *   4. Decode with TextDecoder('utf-8', {fatal:false}) + {stream:true}.
 *   5. Append decoded text to buffer; split on '\n\n'.
 *   6. Parse each complete record → fire appropriate handler.
 *   7. On `done` event → return Result.ok.
 *   8. On `error` event → call handlers.onError, return Result.err(ChatStreamError).
 *   9. On abort → return Result.ok (caller knows it cancelled).
 *  10. reader.releaseLock() in finally.
 *
 * §D-T002-STREAM-DONE-GUARD: if the stream closes without `event: done`, return
 *   ChatNetworkError so useChatStream transitions to error_network (not stuck in streaming).
 *
 * @param conversationId - Conversation UUID.
 * @param message - User message text. NOT logged.
 * @param handlers - Callbacks fired per event type.
 * @param options - Signal for abort, onAuthFailure callback.
 * @returns Result.ok on clean done/abort; Result.err on error.
 */
export async function streamConversation(
  conversationId: string,
  message: string,
  handlers: StreamHandlers,
  options: StreamOptions,
): Promise<Result<void, ChatError>> {
  logVerbose("chat.stream.start", {
    conversation_id: conversationId.slice(0, 8),
    message_len: message.length,
  });

  const url = `/api/v1/chat/conversations/${conversationId}/stream`;

  let response: Response;
  try {
    response = await authFetch(
      url,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
        signal: options.signal,
      },
      { onAuthFailure: options.onAuthFailure },
    );
  } catch (err: unknown) {
    // AbortError means the caller cancelled — return ok
    if (err instanceof DOMException && err.name === "AbortError") {
      logVerbose("chat.stream.aborted", { conversation_id: conversationId.slice(0, 8) });
      return { ok: true, value: undefined };
    }
    const domainErr = mapChatError(err);
    logError("chat.stream.fetch_error", {
      conversation_id: conversationId.slice(0, 8),
      error: domainErr.code,
    });
    return { ok: false, error: domainErr };
  }

  const requestId = response.headers.get("x-request-id") ?? "unknown";

  // Map non-200 statuses before touching the stream body
  if (!response.ok) {
    logError("chat.stream.http_error", {
      conversation_id: conversationId.slice(0, 8),
      status: response.status,
      request_id: requestId,
    });
    if (response.status === 400) {
      return { ok: false, error: new ChatValidationError() };
    }
    if (response.status === 401) {
      return { ok: false, error: new ChatAuthExpiredError() };
    }
    if (response.status === 403) {
      return { ok: false, error: new ChatForbiddenError() };
    }
    if (response.status === 404) {
      return { ok: false, error: new ChatNotFoundError() };
    }
    return { ok: false, error: new ChatServerError(response.status) };
  }

  if (!response.body) {
    logError("chat.stream.no_body", { conversation_id: conversationId.slice(0, 8) });
    return { ok: false, error: new ChatNetworkError("No response body") };
  }

  // Read the stream
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: false });
  let buffer = "";
  let eventCount = 0;
  // §D-T002-STREAM-DONE-GUARD: track whether backend emitted `event: done`.
  // If the ReadableStream ends without it (e.g. LiteLLM drops after meta),
  // return ChatNetworkError so useChatStream transitions to error_network.
  let doneEmitted = false;

  logVerbose("chat.stream.reading", {
    conversation_id: conversationId.slice(0, 8),
    request_id: requestId,
  });

  try {
    while (true) {
      let readResult: ReadableStreamReadResult<Uint8Array>;
      try {
        readResult = await reader.read();
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          logVerbose("chat.stream.aborted_during_read", {
            conversation_id: conversationId.slice(0, 8),
          });
          return { ok: true, value: undefined };
        }
        const domainErr = mapChatError(err);
        logError("chat.stream.read_error", {
          conversation_id: conversationId.slice(0, 8),
          error: domainErr.code,
        });
        return { ok: false, error: domainErr };
      }

      const { done, value } = readResult;

      if (value) {
        buffer += decoder.decode(value, { stream: true });
      }

      if (done) {
        // Flush remaining decoder bytes (non-streaming decode)
        buffer += decoder.decode();
        break;
      }

      // Split on double-newline (SSE record separator)
      const records = buffer.split("\n\n");
      // Last entry is the partial (possibly empty) record — keep in buffer
      buffer = records.pop() ?? "";

      for (const record of records) {
        const event = _parseSseRecord(record);
        if (!event) continue;

        eventCount++;

        switch (event.kind) {
          case "meta":
            logVerbose("chat.stream.event.meta", {
              conversation_id: conversationId.slice(0, 8),
              message_id: event.payload.message_id.slice(0, 8),
            });
            handlers.onMeta(event.payload);
            break;
          case "chunk":
            // Do NOT log delta content (§D-T002-NO-PII-IN-LOGS)
            handlers.onChunk(event.payload);
            break;
          case "citation":
            // Do NOT log label or snippet (§D-T002-NO-PII-IN-LOGS)
            logVerbose("chat.stream.event.citation", {
              conversation_id: conversationId.slice(0, 8),
              document_id: event.payload.document_id,
              score: event.payload.score,
            });
            handlers.onCitation(event.payload);
            break;
          case "usage":
            logVerbose("chat.stream.event.usage", {
              conversation_id: conversationId.slice(0, 8),
              tokens_in: event.payload.tokens_in,
              tokens_out: event.payload.tokens_out,
            });
            handlers.onUsage(event.payload);
            break;
          case "error": {
            logError("chat.stream.event.error", {
              conversation_id: conversationId.slice(0, 8),
              code: event.payload.code,
            });
            handlers.onError(event.payload);
            return {
              ok: false,
              error: new ChatStreamError(event.payload.code, event.payload.message),
            };
          }
          case "done":
            logVerbose("chat.stream.event.done", {
              conversation_id: conversationId.slice(0, 8),
              message_id: event.payload.message_id.slice(0, 8),
              total_events: eventCount,
            });
            doneEmitted = true;
            handlers.onDone(event.payload);
            return { ok: true, value: undefined };
        }
      }
    }

    // Reader signaled done — process any leftover buffer
    if (buffer.trim()) {
      const event = _parseSseRecord(buffer);
      if (event) {
        if (event.kind === "done") {
          doneEmitted = true;
          handlers.onDone(event.payload);
        } else if (event.kind === "error") {
          handlers.onError(event.payload);
          return {
            ok: false,
            error: new ChatStreamError(event.payload.code, event.payload.message),
          };
        }
      } else {
        logWarn("chat.stream.leftover_unparse", {
          conversation_id: conversationId.slice(0, 8),
        });
      }
    }

    // §D-T002-STREAM-DONE-GUARD: the SSE stream closed without `event: done`.
    // This is the LiteLLM-proxy-drops-after-meta case observed in /verify-slice.
    // Without this guard, useChatStream would stay in phase=streaming forever.
    if (!doneEmitted) {
      logWarn("chat.stream.closed_without_done", {
        conversation_id: conversationId.slice(0, 8),
        total_events: eventCount,
      });
      return {
        ok: false,
        error: new ChatNetworkError("Stream closed without done event"),
      };
    }

    logVerbose("chat.stream.complete", {
      conversation_id: conversationId.slice(0, 8),
      total_events: eventCount,
    });
    return { ok: true, value: undefined };
  } finally {
    reader.releaseLock();
  }
}

/**
 * Hilo People — Chat repository (concrete HTTP adapter).
 *
 * Slice/Phase: P03-S02-T001 — ChatHomePage / Phase 3.
 *   Extended in P03-S02-T008 — ConversationPage: added getConversation()
 *   for GET /api/v1/chat/conversations/{id} (§D-T002-REPO-GET).
 *
 * Responsibility: HTTP adapter for chat operations via authFetch.
 *   Returns Result<T, ChatError> — never throws to presentation layer.
 *   Mirrors authRepository.ts pattern: BEFORE/AFTER/ERROR logging, Result shape.
 *
 * Clean Architecture: this is the DATA layer for the chat feature.
 *   Presentation hooks depend on this module, not the raw HTTP client.
 *
 * Security:
 *   - Uses authFetch (X-Request-ID, credentials:include, Bearer injection, single-flight 401).
 *   - Relative URL per ADR-002 (same-origin via vite proxy in dev, Nginx in prod).
 *   - NEVER hardcode http://localhost:8000 here.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR on every public method.
 * Logging rules: NO prompt content, NO token values, NO user.email.
 */

import type { Result } from "../../auth/domain/AuthRepository";
import type {
  CreateConversationRequest,
  Conversation,
  ConversationDetail,
  GetConversationResponse,
  ListConversationsRequest,
  ListConversationsResponse,
} from "../domain/types";
import { authFetch } from "../../auth/data/httpClient";
import {
  ChatValidationError,
  ChatNetworkError,
  ChatAuthExpiredError,
  ChatForbiddenError,
  ChatNotFoundError,
  ChatServerError,
  mapChatError,
  type ChatError,
} from "./errors";
import { logVerbose, logWarn, logError } from "./logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CONVERSATIONS_URL = "/api/v1/chat/conversations";

// ---------------------------------------------------------------------------
// Helper: safely read response JSON
// ---------------------------------------------------------------------------

async function _safeJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) throw new Error("Empty response body");
  return JSON.parse(text) as T;
}

// ---------------------------------------------------------------------------
// Public: createConversation
// ---------------------------------------------------------------------------

/**
 * Calls POST /api/v1/chat/conversations.
 *
 * Returns Result.ok({conversation_id, title, language, created_at}) on 201.
 * Returns typed Result.err for all failure paths (400, 401, 403, 5xx, network).
 *
 * @param request - The conversation creation request (initial_message, language).
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns Result<Conversation, ChatError>
 */
export async function createConversation(
  request: CreateConversationRequest,
  onAuthFailure: () => void,
): Promise<Result<Conversation, ChatError>> {
  logVerbose("chat.repo.createConversation.start", {
    prompt_len: request.initial_message?.length ?? 0,
    language: request.language ?? "default",
  });

  try {
    const response = await authFetch(
      CONVERSATIONS_URL,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      },
      { onAuthFailure },
    );

    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 400) {
      logWarn("chat.repo.createConversation.validation_error", {
        status: 400,
        request_id: requestId,
      });
      return { ok: false, error: new ChatValidationError() };
    }

    if (response.status === 401) {
      // authFetch already attempted refresh. Final 401 = session expired.
      logWarn("chat.repo.createConversation.auth_expired", {
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new ChatAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("chat.repo.createConversation.forbidden", {
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new ChatForbiddenError() };
    }

    if (!response.ok) {
      logError("chat.repo.createConversation.server_error", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new ChatServerError(response.status) };
    }

    const body = await _safeJson<{ data: Conversation }>(response);
    logVerbose("chat.repo.createConversation.ok", {
      conversation_id: body.data.conversation_id,
      language: body.data.language,
      request_id: requestId,
    });

    return { ok: true, value: body.data };
  } catch (err: unknown) {
    const domainErr = mapChatError(err);
    logError("chat.repo.createConversation.error", {
      error: domainErr.code,
      message: domainErr.message,
    });
    return { ok: false, error: domainErr };
  }
}

// ---------------------------------------------------------------------------
// §D-T003-REPO-LIST — listConversations (P03-S02-T003)
// ---------------------------------------------------------------------------

/**
 * Calls GET /api/v1/chat/conversations with optional cursor + limit.
 *
 * Returns Result.ok(ListConversationsResponse) on 200.
 * Returns typed Result.err for all failure paths (401, 403, 5xx, network).
 *
 * Logging rules: BEFORE/AFTER/ERROR — PII-clean.
 *   Log count + has_more only. NEVER log conversation IDs or titles.
 *
 * @param request - Pagination request (cursor, limit, signal).
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns Result<ListConversationsResponse, ChatError>
 */
export async function listConversations(
  request: ListConversationsRequest,
  onAuthFailure: () => void,
): Promise<Result<ListConversationsResponse, ChatError>> {
  const hasCursor = Boolean(request.cursor);
  const limit = request.limit ?? null;

  logVerbose("chat.repo.listConversations.start", {
    has_cursor: hasCursor,
    limit,
  });

  try {
    const params = new URLSearchParams();
    if (request.cursor) params.set("cursor", request.cursor);
    if (request.limit !== undefined) params.set("limit", String(request.limit));
    const qs = params.toString();
    const url = qs
      ? `${CONVERSATIONS_URL}?${qs}`
      : CONVERSATIONS_URL;

    const response = await authFetch(
      url,
      { method: "GET", signal: request.signal },
      { onAuthFailure },
    );

    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 401) {
      logWarn("chat.repo.listConversations.auth_expired", {
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new ChatAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("chat.repo.listConversations.forbidden", {
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new ChatForbiddenError() };
    }

    if (!response.ok) {
      logError("chat.repo.listConversations.server_error", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new ChatServerError(response.status) };
    }

    const body = await _safeJson<ListConversationsResponse>(response);
    const count = body.data.length;
    const hasMore = body.meta.pagination?.has_more ?? false;
    const hasCursorNext = Boolean(body.meta.pagination?.next_cursor);

    logVerbose("chat.repo.listConversations.success", {
      count,
      has_more: hasMore,
      has_cursor_next: hasCursorNext,
      request_id: requestId,
    });

    return { ok: true, value: body };
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      logVerbose("chat.repo.listConversations.aborted");
      return { ok: false, error: new ChatNetworkError("Request aborted", err) };
    }
    const domainErr = mapChatError(err);
    logWarn("chat.repo.listConversations.error", {
      code: domainErr.code,
    });
    return { ok: false, error: domainErr };
  }
}

// ---------------------------------------------------------------------------
// §D-T002-REPO-GET — getConversation (P03-S02-T008)
// ---------------------------------------------------------------------------

/**
 * Calls GET /api/v1/chat/conversations/{id}.
 *
 * Returns Result.ok(ConversationDetail) on 200.
 * Returns typed Result.err for all failure paths (401, 403, 404, 5xx, network).
 *
 * §D-T002-403-VS-404: 403 = forbidden (another user's conversation);
 *   404 = not found (UUID does not exist). These are surfaced as distinct errors.
 *
 * Logging rules: BEFORE/AFTER/ERROR — PII-clean.
 *   Log conversation_id prefix and counts only. NEVER log message content.
 *
 * @param id - Conversation UUID.
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns Result<ConversationDetail, ChatError>
 */
export async function getConversation(
  id: string,
  onAuthFailure: () => void,
): Promise<Result<ConversationDetail, ChatError>> {
  logVerbose("chat.repo.getConversation.start", {
    conversation_id: id.slice(0, 8),
  });

  try {
    const url = `${CONVERSATIONS_URL}/${id}`;
    const response = await authFetch(
      url,
      { method: "GET" },
      { onAuthFailure },
    );

    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 401) {
      logWarn("chat.repo.getConversation.auth_expired", {
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new ChatAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("chat.repo.getConversation.forbidden", {
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new ChatForbiddenError() };
    }

    if (response.status === 404) {
      logWarn("chat.repo.getConversation.not_found", {
        status: 404,
        request_id: requestId,
      });
      return { ok: false, error: new ChatNotFoundError() };
    }

    if (!response.ok) {
      logError("chat.repo.getConversation.server_error", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new ChatServerError(response.status) };
    }

    const body = await _safeJson<GetConversationResponse>(response);
    logVerbose("chat.repo.getConversation.ok", {
      conversation_id: body.data.id.slice(0, 8),
      message_count: body.data.messages.length,
      citation_count: body.data.citations.length,
      request_id: requestId,
    });

    return { ok: true, value: body.data };
  } catch (err: unknown) {
    const domainErr = mapChatError(err);
    logError("chat.repo.getConversation.error", {
      error: domainErr.code,
      message: domainErr.message,
    });
    return { ok: false, error: domainErr };
  }
}

/**
 * Hilo People — Chat repository (concrete HTTP adapter).
 *
 * Slice/Phase: P03-S02-T001 — ChatHomePage / Phase 3.
 *   Extended in P03-S02-T002 — ConversationPage: added getConversation
 *   (§D-T002-REPO-GET) for GET /api/v1/chat/conversations/{id}.
 *
 * Responsibility: Calls POST /api/v1/chat/conversations + GET /api/v1/chat/conversations/{id}
 *   via authFetch. Returns Result<T, ChatError> — never throws to presentation layer.
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
 * Logging rules: NO prompt content, NO token values, NO user.email, NO message content.
 */

import type { Result } from "../../auth/domain/AuthRepository";
import type {
  CreateConversationRequest,
  Conversation,
  ConversationDetail,
  GetConversationResponse,
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
// Public: getConversation (§D-T002-REPO-GET)
// ---------------------------------------------------------------------------

/**
 * Calls GET /api/v1/chat/conversations/{id}.
 *
 * Returns Result.ok(ConversationDetail) on 200 with full transcript.
 * Returns typed Result.err for all failure paths (401, 403, 404, 5xx, network).
 *
 * Logging rules: log conversation_id, message count, citation count — NEVER log
 * message content, citation snippets, or user email.
 *
 * @param id - Conversation UUID to fetch.
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns Result<ConversationDetail, ChatError>
 */
export async function getConversation(
  id: string,
  onAuthFailure: () => void,
): Promise<Result<ConversationDetail, ChatError>> {
  logVerbose("chat.repo.getConversation.start", { conversation_id: id });

  try {
    const response = await authFetch(
      `${CONVERSATIONS_URL}/${id}`,
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
        conversation_id: id,
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
    const detail = body.data;

    logVerbose("chat.repo.getConversation.ok", {
      conversation_id: detail.id,
      message_count: detail.messages.length,
      citation_count: detail.citations.length,
      request_id: requestId,
    });

    return { ok: true, value: detail };
  } catch (err: unknown) {
    const domainErr = mapChatError(err);
    logError("chat.repo.getConversation.error", {
      error: domainErr.code,
      conversation_id: id,
    });
    return { ok: false, error: domainErr };
  }
}

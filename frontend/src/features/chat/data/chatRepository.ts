/**
 * Hilo People — Chat repository (concrete HTTP adapter).
 *
 * Slice/Phase: P03-S02-T001 — ChatHomePage / Phase 3.
 *
 * Responsibility: Calls POST /api/v1/chat/conversations via authFetch.
 *   Returns Result<Conversation, ChatError> — never throws to presentation layer.
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
import type { CreateConversationRequest, Conversation } from "../domain/types";
import { authFetch } from "../../auth/data/httpClient";
import {
  ChatValidationError,
  ChatNetworkError,
  ChatAuthExpiredError,
  ChatForbiddenError,
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

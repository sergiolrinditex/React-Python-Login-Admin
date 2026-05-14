/**
 * Hilo People — Chat domain errors.
 *
 * Slice/Phase: P03-S02-T001 — ChatHomePage / Phase 3.
 *   Extended in P03-S02-T002 — ConversationPage: added ChatNotFoundError (§D-T002-ERRORS-EXTEND)
 *   and ChatStreamError (mid-stream `event: error` handler).
 *
 * Responsibility: Typed error classes for chat operations.
 *   chatRepository.ts returns these via Result<T,E> patterns.
 *   Non-negotiables §error-handling: never catch generic Error — use typed domain errors.
 *
 * Mirrors the pattern from features/auth/data/errors.ts.
 * Source: TECHNICAL_GUIDE §6.2 — error envelope {errors:[{code,message,field?,details?}]}.
 */

// ---------------------------------------------------------------------------
// Chat error classes
// ---------------------------------------------------------------------------

/**
 * Validation error — server returned 400 or client-side validation failed.
 * Used for empty input, max-length exceeded, or invalid language codes.
 */
export class ChatValidationError extends Error {
  public readonly code = "CHAT_VALIDATION_ERROR";

  constructor(message = "Invalid conversation request.") {
    super(message);
    this.name = "ChatValidationError";
  }
}

/**
 * Network error — fetch rejected (offline, CORS, DNS failure).
 * Does NOT indicate an auth failure — may be a transient connectivity issue.
 */
export class ChatNetworkError extends Error {
  public readonly code = "CHAT_NETWORK_ERROR";

  constructor(message = "Network request failed.", public readonly cause?: unknown) {
    super(message);
    this.name = "ChatNetworkError";
  }
}

/**
 * Session expired — server returned 401 after refresh exhausted.
 * Handled by authFetch single-flight; surfaces here when recovery is impossible.
 */
export class ChatAuthExpiredError extends Error {
  public readonly code = "CHAT_AUTH_EXPIRED";

  constructor(message = "Session expired. Please sign in again.") {
    super(message);
    this.name = "ChatAuthExpiredError";
  }
}

/**
 * Forbidden — server returned 403 (employee role missing or insufficient).
 */
export class ChatForbiddenError extends Error {
  public readonly code = "CHAT_FORBIDDEN";

  constructor(message = "You do not have permission to perform this action.") {
    super(message);
    this.name = "ChatForbiddenError";
  }
}

/**
 * Server error — 5xx response.
 */
export class ChatServerError extends Error {
  public readonly code = "CHAT_SERVER_ERROR";
  public readonly status: number;

  constructor(status: number, message = "Server error.") {
    super(message);
    this.name = "ChatServerError";
    this.status = status;
  }
}

/**
 * Not found error — server returned 404 (conversation does not exist for this user).
 * §D-T002-403-VS-404: 404 ≠ forbidden. Shows "not found" empty state.
 */
export class ChatNotFoundError extends Error {
  public readonly code = "CHAT_NOT_FOUND";

  constructor(message = "Conversation not found.") {
    super(message);
    this.name = "ChatNotFoundError";
  }
}

/**
 * Stream error — server emitted `event: error` mid-stream.
 * §D-T002-STREAM-MODULE: surface from SSE parser as a typed domain error.
 * code = the machine-readable code from the server payload (e.g. "STREAM_ERROR").
 */
export class ChatStreamError extends Error {
  public readonly code = "CHAT_STREAM_ERROR";
  public readonly serverCode: string;

  constructor(serverCode: string, message = "Stream error from server.") {
    super(message);
    this.name = "ChatStreamError";
    this.serverCode = serverCode;
  }
}

/** Union of all typed chat errors. */
export type ChatError =
  | ChatValidationError
  | ChatNetworkError
  | ChatAuthExpiredError
  | ChatForbiddenError
  | ChatNotFoundError
  | ChatStreamError
  | ChatServerError;

// ---------------------------------------------------------------------------
// Error mapper
// ---------------------------------------------------------------------------

/**
 * Maps an unknown fetch/domain error to a typed ChatError.
 *
 * @param err - Raw caught value from a try/catch block.
 * @returns A typed domain error.
 */
export function mapChatError(err: unknown): ChatError {
  if (err instanceof ChatValidationError) return err;
  if (err instanceof ChatNetworkError) return err;
  if (err instanceof ChatAuthExpiredError) return err;
  if (err instanceof ChatForbiddenError) return err;
  if (err instanceof ChatNotFoundError) return err;
  if (err instanceof ChatStreamError) return err;
  if (err instanceof ChatServerError) return err;
  if (err instanceof TypeError) {
    return new ChatNetworkError(err.message, err);
  }
  if (err instanceof Error) return new ChatNetworkError(err.message, err);
  return new ChatNetworkError("Unknown error");
}

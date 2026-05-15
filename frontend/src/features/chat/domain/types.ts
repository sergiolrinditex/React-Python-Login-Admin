/**
 * Hilo People — Chat domain types (entities and DTOs).
 *
 * Slice/Phase: P03-S02-T001 — ChatHomePage / Phase 3.
 *
 * Responsibility: Pure TypeScript types for the chat domain.
 *   No React, no external libraries, no fetch, no side effects.
 *   Downstream layers (data/, presentation/) depend on these types.
 *
 * Source: TECHNICAL_GUIDE §6.2 — POST /api/v1/chat/conversations contract (P02-S03-T001).
 *   Matches backend/app/chat/schemas.py (D-TX1 — atomic conversation + message write).
 *
 * Dependency: imports UserProfile from auth domain (read-only, no auth mutation).
 */

// ---------------------------------------------------------------------------
// Conversation entity
// ---------------------------------------------------------------------------

/** Supported languages — matches backend enum and UserProfile.preferred_language. */
export type SupportedLanguage = "es" | "en" | "fr";

/**
 * Minimal conversation snapshot returned by POST /api/v1/chat/conversations.
 * Source: backend/app/chat/schemas.py — CreateConversationResponse (D-TX1).
 *
 * NOTE: Actual backend (P02-S03-T001) returns only {conversation_id}.
 * title, language, created_at are omitted in the real response envelope.
 * Future fields (title, language) are typed as optional for forward compatibility.
 */
export interface Conversation {
  conversation_id: string;
  title?: string;
  language?: SupportedLanguage;
  created_at?: string;
}

// ---------------------------------------------------------------------------
// Request / Response DTOs
// ---------------------------------------------------------------------------

/**
 * Request body for POST /api/v1/chat/conversations.
 * Both fields optional per TECHNICAL_GUIDE §6.2; backend falls back to user language (D-LANG1).
 */
export interface CreateConversationRequest {
  initial_message?: string;
  language?: SupportedLanguage;
}

/**
 * Response envelope for POST /api/v1/chat/conversations → 201.
 * Common envelope: { data: Conversation }.
 */
export interface CreateConversationResponse {
  data: Conversation;
}

// ---------------------------------------------------------------------------
// Chat error codes
// ---------------------------------------------------------------------------

/** Error codes surfaced from the chat API layer. */
export type ChatErrorCode =
  | "CHAT_VALIDATION_ERROR"
  | "CHAT_NETWORK_ERROR"
  | "CHAT_AUTH_EXPIRED"
  | "CHAT_FORBIDDEN"
  | "CHAT_SERVER_ERROR"
  | "CHAT_UNKNOWN";

// ---------------------------------------------------------------------------
// §D-T003-DOMAIN-SUMMARY — HistoryPage domain types (P03-S02-T003)
// ---------------------------------------------------------------------------

/**
 * Opaque cursor string for paginated conversation list (D-PAG1: base64url of (updated_at, id)).
 * Never decode on the frontend — pass as-is to the next request.
 */
export type Cursor = string;

/**
 * Conversation summary returned by GET /api/v1/chat/conversations.
 * Source: backend/app/chat/schemas.py — ConversationDTO.
 * Matches TECHNICAL_GUIDE §6.2 list endpoint shape.
 *
 * NOTE: title may be null/empty from backend (auto-generated after first message).
 * Use fallback i18n key `history.untitledConversation` when title is falsy.
 */
export interface ConversationSummary {
  id: string;
  user_id: string | null;
  title: string | null;
  language: SupportedLanguage;
  created_at: string;   // ISO-8601 UTC
  updated_at: string;   // ISO-8601 UTC — used for grouping and sort order (D-PAG1)
}

/**
 * Request params for GET /api/v1/chat/conversations.
 * cursor is optional (omit → first page). limit is optional (backend default applies).
 */
export interface ListConversationsRequest {
  cursor?: Cursor;
  limit?: number;
  signal?: AbortSignal;
}

/**
 * Pagination metadata returned in meta.pagination.
 * Source: PaginationMeta in backend/app/chat/schemas.py.
 */
export interface PaginationMeta {
  next_cursor: Cursor | null;
  has_more: boolean;
}

/**
 * Response envelope for GET /api/v1/chat/conversations → 200.
 * Common envelope: { data: ConversationSummary[], meta: { request_id, pagination } }.
 */
export interface ListConversationsResponse {
  data: ConversationSummary[];
  meta: {
    request_id: string;
    pagination: PaginationMeta | null;
  };
  errors: unknown[];
}

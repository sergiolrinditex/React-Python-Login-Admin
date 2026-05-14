/**
 * Hilo People — Chat domain types (entities and DTOs).
 *
 * Slice/Phase: P03-S02-T001 — ChatHomePage / Phase 3.
 *   Extended in P03-S02-T002 — ConversationPage: added Message, MessageCitation,
 *   ConversationDetail, GetConversationResponse, and SSE event discriminated union.
 *
 * Responsibility: Pure TypeScript types for the chat domain.
 *   No React, no external libraries, no fetch, no side effects.
 *   Downstream layers (data/, presentation/) depend on these types.
 *
 * Source: TECHNICAL_GUIDE §6.2 — POST /api/v1/chat/conversations contract (P02-S03-T001).
 *   §D-T002-DOMAIN-DETAIL: ConversationDetail, Message, MessageCitation, SSE events.
 *   Matches backend/app/chat/schemas.py (D-TX1 — atomic conversation + message write).
 *   SSE event shapes match backend/app/chat/streaming/sse.py functions.
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
// Conversation detail (§D-T002-DOMAIN-DETAIL)
// ---------------------------------------------------------------------------

/**
 * A single message within a conversation.
 * Matches backend app/chat/schemas.py MessageResponse shape.
 * Source: TECHNICAL_GUIDE §6.3.
 */
export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  token_count: number | null;
  created_at: string;
}

/**
 * A RAG citation linked to a specific assistant message.
 * Matches backend app/chat/schemas.py CitationResponse shape.
 * Source: TECHNICAL_GUIDE §6.3.
 */
export interface MessageCitation {
  id: string;
  message_id: string;
  document_id: string | null;
  chunk_id: string | null;
  label: string;
  score: number;
}

/**
 * Full conversation detail returned by GET /api/v1/chat/conversations/{id}.
 * Contains the complete transcript (messages) and all citations.
 * Source: TECHNICAL_GUIDE §6.2 — GetConversationResponse.
 */
export interface ConversationDetail {
  id: string;
  user_id: string | null;
  title: string;
  language: SupportedLanguage;
  created_at: string;
  updated_at: string;
  messages: Message[];
  citations: MessageCitation[];
}

/**
 * Response envelope for GET /api/v1/chat/conversations/{id} → 200.
 * Common envelope: { data: ConversationDetail, meta: {...}, errors: [] }.
 */
export interface GetConversationResponse {
  data: ConversationDetail;
  meta: { request_id: string };
  errors: unknown[];
}

// ---------------------------------------------------------------------------
// SSE event types (§D-T002-DOMAIN-DETAIL)
// Shapes match backend app/chat/streaming/sse.py functions.
// Order in V1: meta → citation* → chunk* → usage → done | error
// ---------------------------------------------------------------------------

/** meta event — one per stream, before any chunks. */
export interface SseMetaEvent {
  kind: "meta";
  payload: {
    message_id: string;
    model_id: string;
    language: string;
    request_id: string;
  };
}

/** chunk event — incremental text fragment from LLM. */
export interface SseChunkEvent {
  kind: "chunk";
  payload: {
    delta: string;
  };
}

/** citation event — RAG source citation (0..N per stream, before chunks). */
export interface SseCitationEvent {
  kind: "citation";
  payload: {
    document_id: string;
    chunk_id: string;
    label: string;
    score: number;
  };
}

/** usage event — token and cost accounting. */
export interface SseUsageEvent {
  kind: "usage";
  payload: {
    tokens_in: number;
    tokens_out: number;
    estimated_cost: number;
    latency_ms: number;
  };
}

/** error event — mid-stream fatal error from server. */
export interface SseErrorEvent {
  kind: "error";
  payload: {
    code: string;
    message: string;
  };
}

/** done event — terminal event; stream is complete. */
export interface SseDoneEvent {
  kind: "done";
  payload: {
    message_id: string;
    request_id: string;
  };
}

/** Discriminated union of all SSE event types. */
export type SseEvent =
  | SseMetaEvent
  | SseChunkEvent
  | SseCitationEvent
  | SseUsageEvent
  | SseErrorEvent
  | SseDoneEvent;

// ---------------------------------------------------------------------------
// Chat error codes
// ---------------------------------------------------------------------------

/** Error codes surfaced from the chat API layer. */
export type ChatErrorCode =
  | "CHAT_VALIDATION_ERROR"
  | "CHAT_NETWORK_ERROR"
  | "CHAT_AUTH_EXPIRED"
  | "CHAT_FORBIDDEN"
  | "CHAT_NOT_FOUND"
  | "CHAT_STREAM_ERROR"
  | "CHAT_SERVER_ERROR"
  | "CHAT_UNKNOWN";

/**
 * Hilo People — ConversationPage (§D-T002-PAGE).
 *
 * Slice/Phase: P03-S02-T008 — ConversationPage re-implementation / Phase 3.
 *   Re-implemented from reference branch f7f5f33 (P03-S02-T002).
 *   Updated P03-S02-T009: mounts ChatNavbar in non-forbidden branches
 *   (§D-T009-NAVBAR-PLACEMENT-INSIDE-PAGE, §D-T009-NAVBAR-VISIBILITY).
 *
 * Responsibility: Employee conversation screen at /chat/:conversationId.
 *   Streams RAG-cited assistant responses over SSE. Implements all 7 required
 *   UX states: loading, empty, streaming, error_network, error_validation,
 *   permission_denied, success.
 *
 * Decisions applied:
 *   §D-T002-DEEP-LINK: auto-streams when GET returns a conversation whose last
 *     message is user-role with no assistant reply (first turn from ChatHomePage).
 *     Resume mode (back-nav from /history or cold load): no auto-stream.
 *   §D-T002-CITATIONS-INLINE: transcript uses no-bubble editorial layout.
 *     TrackedLabel for role hairlines; serif (--font-display) for assistant;
 *     sans (--font-sans) for user. CitationInline chips cluster at end of
 *     assistant message block, ordered by arrival.
 *   §D-T002-ABORT-ON-UNMOUNT: useChatStream owns AbortController.
 *   §D-T002-TANSTACK-CACHE: on done, setQueryData updates cache without refetch.
 *   §D-T002-ROUTE: registered in router.tsx (§D-T002-ROUTE anchor).
 *   §D-T002-ACCESSIBILITY: aria-live + aria-busy on streaming region.
 *   §D-T002-FILE-SIZE-DISCIPLINE: styles → ConversationPage.styles.ts;
 *     error sub-views → _ConversationPage.error-views.tsx.
 *
 * Security: no PII in logs. No token storage in component state.
 * Route: /chat/:conversationId (RequireAuth employee).
 * Journey refs: J101 (first turn after ChatHomePage), J102 (resume from /history).
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR gated by VITE_ENABLE_VERBOSE_LOGGING.
 */

import { type ReactNode, useCallback, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import MobileFrame from "../../shared/design-system/MobileFrame";
import TrackedLabel from "../../shared/design-system/TrackedLabel";
import CitationInline from "../../shared/design-system/CitationInline";
import Composer from "../../features/chat/presentation/Composer";
import { useAuth } from "../../features/auth/presentation/AuthProvider";
import { useConversation } from "../../features/chat/presentation/useConversation";
import { useChatStream } from "../../features/chat/presentation/useChatStream";
import {
  ForbiddenView,
  NotFoundView,
  NetworkErrorView,
  ValidationErrorBanner,
  EmptyView,
} from "./_ConversationPage.error-views";
import {
  PAGE_STYLE,
  HEADER_STYLE,
  TRANSCRIPT_STYLE,
  MESSAGE_BLOCK_STYLE,
  USER_TEXT_STYLE,
  ASSISTANT_TEXT_STYLE,
  CITATIONS_ROW_STYLE,
  LOADING_STYLE,
  CURSOR_STYLE,
} from "./ConversationPage.styles";
import { ROUTE_CHAT } from "../../app/router";
import { logVerbose, logWarn, logError } from "../../features/chat/data/logger";
import ChatNavbar from "./_ChatNavbar";
import type { Message, MessageCitation } from "../../features/chat/domain/types";

// ---------------------------------------------------------------------------
// MessageBlock sub-component
// ---------------------------------------------------------------------------

interface MessageBlockProps {
  message: Message;
  citations: MessageCitation[];
  youLabel: string;
  assistantLabel: string;
}

/**
 * Renders one conversation turn (user or assistant) with no-bubble editorial layout.
 * §D-T002-CITATIONS-INLINE: CitationInline chips cluster at end of assistant block.
 */
function MessageBlock({
  message,
  citations,
  youLabel,
  assistantLabel,
}: MessageBlockProps): ReactNode {
  const isAssistant = message.role === "assistant";
  const label = isAssistant ? assistantLabel : youLabel;
  const textStyle = isAssistant ? ASSISTANT_TEXT_STYLE : USER_TEXT_STYLE;

  return (
    <div style={MESSAGE_BLOCK_STYLE} data-testid={`message-block-${message.role}`}>
      <TrackedLabel variant="muted">{label}</TrackedLabel>
      <p style={textStyle}>{message.content}</p>
      {isAssistant && citations.length > 0 && (
        <div style={CITATIONS_ROW_STYLE} aria-label="Sources">
          {citations.map((cit) => (
            <CitationInline
              key={cit.id}
              label={cit.label}
              aria-label={`Source: ${cit.label}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ConversationPage
// ---------------------------------------------------------------------------

/**
 * Employee conversation page — real-time SSE streaming with editorial transcript.
 *
 * @returns ConversationPage element.
 */
export default function ConversationPage(): ReactNode {
  const { conversationId } = useParams<{ conversationId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation(["chat", "errors", "common"]);
  const { logout } = useAuth();

  logVerbose("chat.conversation.render.start", {
    conversation_id: conversationId?.slice(0, 8),
  });

  // Auth failure handler
  const handleAuthFailure = useCallback((): void => {
    logWarn("chat.conversation.auth_failure");
    void logout();
  }, [logout]);

  const { data: conversation, status, error: queryError, isLoading } =
    useConversation(conversationId, handleAuthFailure);

  const { phase, assistantText, citations, lastError, start, retry } =
    useChatStream(conversationId ?? "", handleAuthFailure);

  // Track whether auto-stream has fired (prevent double-fire in StrictMode)
  const autoStreamFiredRef = useRef(false);

  // §D-T002-DEEP-LINK: auto-stream if last message is user with no assistant reply
  useEffect(() => {
    if (
      !conversation ||
      phase !== "idle" ||
      autoStreamFiredRef.current
    ) return;

    const msgs = conversation.messages;
    if (msgs.length === 0) return;

    const lastMsg = msgs[msgs.length - 1];
    if (lastMsg.role !== "user") return;

    // Check there's no assistant reply after this user message
    const hasAssistantAfter = msgs
      .slice(msgs.indexOf(lastMsg) + 1)
      .some((m) => m.role === "assistant");
    if (hasAssistantAfter) return;

    autoStreamFiredRef.current = true;
    logVerbose("chat.conversation.auto_stream", {
      conversation_id: conversationId?.slice(0, 8),
      message_len: lastMsg.content.length,
    });
    start(lastMsg.content);
  }, [conversation, phase, start, conversationId]);

  // ---------------------------------------------------------------------------
  // Navigation handlers
  // ---------------------------------------------------------------------------

  const handleBackToChat = useCallback((): void => {
    logVerbose("chat.conversation.navigate.chat_home");
    void navigate(ROUTE_CHAT);
  }, [navigate]);

  const handleComposerSubmit = useCallback(
    (message: string): void => {
      logVerbose("chat.conversation.composer.submit", { message_len: message.length });
      autoStreamFiredRef.current = true; // Prevent auto-stream from firing again
      start(message);
    },
    [start],
  );

  // ---------------------------------------------------------------------------
  // State derivation
  // ---------------------------------------------------------------------------

  // Error states from GET detail
  const isQueryForbidden = queryError?.code === "CHAT_FORBIDDEN";
  const isQueryNotFound = queryError?.code === "CHAT_NOT_FOUND";

  // Streaming error states
  const isStreamForbidden = phase === "permission_denied";
  const isStreamNotFound = phase === "not_found";
  const isStreamNetworkError = phase === "error_network" || phase === "error_stream";
  const isStreamValidationError = phase === "error_validation";
  const isStreaming = phase === "streaming";

  // Composer disabled while streaming
  const composerDisabled = isStreaming;

  // Conversation title fallback
  const headerTitle = conversation?.title ?? t("chat:conversation.title");

  // citations by message_id for transcript rendering
  const citationsByMessageId = (conversation?.citations ?? []).reduce<
    Record<string, MessageCitation[]>
  >((acc, cit) => {
    acc[cit.message_id] = [...(acc[cit.message_id] ?? []), cit];
    return acc;
  }, {});

  // ---------------------------------------------------------------------------
  // Render: permission_denied (from GET or stream)
  // ---------------------------------------------------------------------------
  if (isQueryForbidden || isStreamForbidden) {
    logError("chat.conversation.render.forbidden", {
      conversation_id: conversationId?.slice(0, 8),
    });
    return (
      <MobileFrame asMain fullHeight>
        <div style={PAGE_STYLE} data-testid="conversation-page">
          <ForbiddenView onBack={handleBackToChat} />
        </div>
      </MobileFrame>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: not_found (from GET or stream — §D-T002-403-VS-404)
  // ---------------------------------------------------------------------------
  if (isQueryNotFound || isStreamNotFound) {
    logWarn("chat.conversation.render.not_found", {
      conversation_id: conversationId?.slice(0, 8),
    });
    return (
      <MobileFrame asMain fullHeight>
        {/* §D-T009-NAVBAR-VISIBILITY: visible in not_found branch (not forbidden) */}
        <ChatNavbar />
        <div style={PAGE_STYLE} data-testid="conversation-page">
          <NotFoundView onNewConversation={handleBackToChat} />
        </div>
      </MobileFrame>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: loading (GET in-flight)
  // ---------------------------------------------------------------------------
  if (isLoading || status === "pending") {
    return (
      <MobileFrame asMain fullHeight>
        {/* §D-T009-NAVBAR-VISIBILITY: visible during loading */}
        <ChatNavbar />
        <div
          style={PAGE_STYLE}
          data-testid="conversation-page"
          aria-busy="true"
        >
          <div style={HEADER_STYLE}>
            <TrackedLabel>{t("chat:conversation.loading.label")}</TrackedLabel>
          </div>
          <p style={LOADING_STYLE}>{t("common:states.loading")}</p>
        </div>
      </MobileFrame>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: empty (GET success, 0 messages, no streaming)
  // ---------------------------------------------------------------------------
  const messages = conversation?.messages ?? [];
  if (status === "success" && messages.length === 0 && phase === "idle") {
    return (
      <MobileFrame asMain fullHeight>
        {/* §D-T009-NAVBAR-VISIBILITY: visible in empty state */}
        <ChatNavbar />
        <div style={PAGE_STYLE} data-testid="conversation-page">
          <div style={HEADER_STYLE}>
            <TrackedLabel>{headerTitle}</TrackedLabel>
          </div>
          <EmptyView onNewConversation={handleBackToChat} />
        </div>
      </MobileFrame>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: main transcript view (success / streaming / errors after content)
  // ---------------------------------------------------------------------------
  return (
    <MobileFrame asMain fullHeight>
      {/* §D-T009-NAVBAR-VISIBILITY: visible in success/streaming/error branches */}
      <ChatNavbar />
      <div style={PAGE_STYLE} data-testid="conversation-page">
        {/* Header */}
        <div style={HEADER_STYLE}>
          <TrackedLabel variant="active">{headerTitle}</TrackedLabel>
        </div>

        {/* Transcript region — §D-T002-ACCESSIBILITY */}
        <div
          role="log"
          aria-live="polite"
          aria-label="Conversation transcript"
          aria-busy={isStreaming ? "true" : undefined}
          style={TRANSCRIPT_STYLE}
          data-testid="transcript-region"
        >
          {/* Persisted messages */}
          {messages.map((msg) => (
            <MessageBlock
              key={msg.id}
              message={msg}
              citations={citationsByMessageId[msg.id] ?? []}
              youLabel={t("chat:conversation.you")}
              assistantLabel={t("chat:conversation.assistant")}
            />
          ))}

          {/* Streaming assistant message (growing in real-time) */}
          {isStreaming && assistantText && (
            <div
              style={MESSAGE_BLOCK_STYLE}
              data-testid="streaming-message"
              aria-busy="true"
            >
              <TrackedLabel variant="muted">
                {t("chat:conversation.streaming.label")}
              </TrackedLabel>
              <p style={ASSISTANT_TEXT_STYLE}>
                {assistantText}
                <span style={CURSOR_STYLE} aria-hidden="true">▍</span>
              </p>
              {/* Citations that arrived before/during chunks */}
              {citations.length > 0 && (
                <div
                  style={CITATIONS_ROW_STYLE}
                  aria-label={t("chat:conversation.citations.label")}
                >
                  {citations.map((cit, idx) => (
                    <CitationInline
                      key={`stream-cit-${idx}`}
                      label={cit.label}
                      aria-label={`Source: ${cit.label}`}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Streaming with no text yet — cursor only */}
          {isStreaming && !assistantText && (
            <div style={MESSAGE_BLOCK_STYLE} data-testid="streaming-placeholder">
              <TrackedLabel variant="muted">
                {t("chat:conversation.streaming.label")}
              </TrackedLabel>
              <p style={ASSISTANT_TEXT_STYLE}>
                <span style={CURSOR_STYLE} aria-hidden="true">▍</span>
              </p>
            </div>
          )}
        </div>

        {/* Network error banner + retry CTA */}
        {isStreamNetworkError && (
          <NetworkErrorView onRetry={retry} />
        )}

        {/* Validation error banner (inline, composer stays) */}
        {isStreamValidationError && lastError && (
          <ValidationErrorBanner
            message={t("chat:composer.errors.tooLong", { max: 4000 })}
          />
        )}

        {/* Composer — always shown unless forbidden/not-found */}
        <Composer
          onSubmit={handleComposerSubmit}
          disabled={composerDisabled}
          loading={isStreaming}
        />
      </div>
    </MobileFrame>
  );
}

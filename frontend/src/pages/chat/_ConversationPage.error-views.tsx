/**
 * Hilo People — ConversationPage error sub-views (§D-T002-PAGE-SPLIT-ERRORVIEWS).
 *
 * Slice/Phase: P03-S02-T008 — ConversationPage re-implementation / Phase 3.
 *   Re-implemented from reference branch f7f5f33 (P03-S02-T002).
 *
 * Responsibility: Error and empty state sub-views for ConversationPage.
 *   Split out from ConversationPage.tsx per §D-T002-FILE-SIZE-DISCIPLINE to
 *   keep the main file under the ~300 substantive-lines cap.
 *
 * States rendered:
 *   - ForbiddenView (permission_denied — 403)
 *   - NotFoundView (not_found — 404)
 *   - NetworkErrorView (error_network with retry CTA)
 *   - ValidationErrorBanner (error_validation inline below composer)
 *   - EmptyView (success with 0 messages, no streaming queued)
 *
 * Token usage: --color-ink, --color-paper, --font-sans, --hairline.
 * No hardcoded colors, no border-radius.
 *
 * Key deps: React, react-i18next, shared design-system.
 */

import type { CSSProperties, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import SolidCTA from "../../shared/design-system/SolidCTA";
import TrackedLabel from "../../shared/design-system/TrackedLabel";

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const VIEW_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
  padding: "1.5rem 0",
};

const TEXT_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.85,
  lineHeight: 1.5,
};

// ---------------------------------------------------------------------------
// ForbiddenView
// ---------------------------------------------------------------------------

interface ForbiddenViewProps {
  onBack: () => void;
}

/**
 * permission_denied state — HTTP 403.
 * Full-screen overlay with return CTA.
 */
export function ForbiddenView({ onBack }: ForbiddenViewProps): ReactNode {
  const { t } = useTranslation(["chat", "common"]);
  return (
    <div
      style={VIEW_STYLE}
      role="status"
      aria-live="assertive"
      data-testid="forbidden-view"
    >
      <TrackedLabel as="p" variant="active">
        {t("chat:conversation.errors.permission.title")}
      </TrackedLabel>
      <SolidCTA
        onClick={onBack}
        aria-label={t("chat:conversation.errors.permission.cta")}
        data-testid="forbidden-back-cta"
      >
        {t("chat:conversation.errors.permission.cta")}
      </SolidCTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NotFoundView
// ---------------------------------------------------------------------------

interface NotFoundViewProps {
  onNewConversation: () => void;
}

/**
 * not_found state — HTTP 404 (§D-T002-403-VS-404).
 * Shows "conversation not found" with CTA back to /chat.
 */
export function NotFoundView({ onNewConversation }: NotFoundViewProps): ReactNode {
  const { t } = useTranslation(["chat", "common"]);
  return (
    <div
      style={VIEW_STYLE}
      role="status"
      aria-live="assertive"
      data-testid="not-found-view"
    >
      <TrackedLabel as="p" variant="active">
        {t("chat:conversation.errors.notFound.title")}
      </TrackedLabel>
      <SolidCTA
        onClick={onNewConversation}
        aria-label={t("chat:conversation.errors.notFound.cta")}
        data-testid="not-found-cta"
      >
        {t("chat:conversation.errors.notFound.cta")}
      </SolidCTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NetworkErrorView
// ---------------------------------------------------------------------------

interface NetworkErrorViewProps {
  onRetry: () => void;
  loading?: boolean;
}

/**
 * error_network state — fetch failure, 5xx, or mid-stream drop.
 * Retry CTA reopens the POST stream with same message (§D-T002-RETRY-SAME-PROMPT).
 */
export function NetworkErrorView({ onRetry, loading = false }: NetworkErrorViewProps): ReactNode {
  const { t } = useTranslation(["chat", "common"]);
  return (
    <div
      style={VIEW_STYLE}
      role="status"
      aria-live="assertive"
      data-testid="network-error-view"
    >
      <p style={TEXT_STYLE}>{t("chat:conversation.errors.network.title")}</p>
      <SolidCTA
        onClick={onRetry}
        loading={loading}
        loadingLabel="…"
        aria-label={t("chat:conversation.errors.network.retry")}
        data-testid="network-error-retry-cta"
      >
        {t("chat:conversation.errors.network.retry")}
      </SolidCTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ValidationErrorBanner
// ---------------------------------------------------------------------------

interface ValidationErrorBannerProps {
  message: string;
}

/**
 * error_validation state — 400 from server or client validation.
 * Renders inline below the composer; does NOT clear it (§D-T002-VALIDATION-STATE).
 */
export function ValidationErrorBanner({ message }: ValidationErrorBannerProps): ReactNode {
  return (
    <p
      role="alert"
      aria-live="assertive"
      style={{ ...TEXT_STYLE, opacity: 1 }}
      data-testid="validation-error-banner"
    >
      {message}
    </p>
  );
}

// ---------------------------------------------------------------------------
// EmptyView
// ---------------------------------------------------------------------------

interface EmptyViewProps {
  onNewConversation: () => void;
}

/**
 * empty state — GET returned 0 messages and no streaming queued.
 * Rare: happens when a conversation was created but the first prompt never submitted.
 */
export function EmptyView({ onNewConversation }: EmptyViewProps): ReactNode {
  const { t } = useTranslation(["chat"]);
  return (
    <div
      style={VIEW_STYLE}
      role="status"
      data-testid="empty-conversation-view"
    >
      <TrackedLabel as="p">{t("chat:conversation.empty.title")}</TrackedLabel>
      <SolidCTA
        onClick={onNewConversation}
        aria-label={t("chat:conversation.empty.cta")}
        data-testid="empty-conversation-cta"
      >
        {t("chat:conversation.empty.cta")}
      </SolidCTA>
    </div>
  );
}

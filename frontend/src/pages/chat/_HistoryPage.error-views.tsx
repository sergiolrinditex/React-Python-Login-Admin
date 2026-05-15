/**
 * Hilo People — HistoryPage error/state sub-views.
 *
 * Slice/Phase: P03-S02-T003 — HistoryPage / Phase 3.
 *
 * Responsibility: LoadingSkeleton, EmptyState, NetworkErrorView, ForbiddenView
 *   sub-components for HistoryPage. Extracted to honor file-size cap (~300 lines).
 *
 * §D-T003-PAGE-SPLIT-ERRORVIEWS — pre-authorized split; mirrors _AccountPage.error-views.tsx
 *   and _ConversationPage.error-views.tsx patterns (T004, T002).
 *
 * Non-negotiables §logging: callers log; these are pure presentation sub-components.
 * Key deps: react-i18next (useTranslation), react-router (useNavigate), design-system.
 */

import { type CSSProperties, type ReactNode, useCallback } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import Wordmark from "../../shared/design-system/Wordmark";
import TrackedLabel from "../../shared/design-system/TrackedLabel";
import SolidCTA from "../../shared/design-system/SolidCTA";
import { logVerbose } from "../../features/chat/data/logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ROUTE_CHAT = "/chat";

// ---------------------------------------------------------------------------
// Styles (tokens only)
// ---------------------------------------------------------------------------

const LOADING_CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.75rem",
  paddingTop: "1.25rem",
};

const SKELETON_ROW_STYLE: CSSProperties = {
  height: "2.75rem",
  background: "var(--color-paper)",
  borderBottom: "var(--hairline)",
  width: "100%",
};

const EMPTY_CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: "1.5rem",
  paddingTop: "3rem",
  paddingBottom: "2rem",
};

const ERROR_CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
  paddingTop: "2rem",
};

const ERROR_TEXT_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.85,
};

const EMPTY_BODY_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.85,
  textAlign: "center",
  margin: 0,
};

// ---------------------------------------------------------------------------
// LoadingSkeleton
// ---------------------------------------------------------------------------

/**
 * Loading state — aria-busy=true skeleton rows.
 * No layout shift on data arrival.
 */
export function LoadingSkeleton(): ReactNode {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Loading"
      data-testid="history-loading"
      style={LOADING_CONTAINER_STYLE}
    >
      {Array.from({ length: 5 }, (_, i) => (
        <div key={i} style={SKELETON_ROW_STYLE} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// EmptyState
// ---------------------------------------------------------------------------

/**
 * Empty state — Wordmark + CTA to start a new chat.
 * Shown when the conversation list is empty (length === 0).
 */
export function EmptyState(): ReactNode {
  const { t } = useTranslation(["history"]);
  const navigate = useNavigate();

  const handleNewChat = useCallback((): void => {
    logVerbose("chat.history.page.empty_cta");
    void navigate(ROUTE_CHAT);
  }, [navigate]);

  return (
    <div
      style={EMPTY_CONTAINER_STYLE}
      data-testid="history-empty"
    >
      <Wordmark />
      <TrackedLabel>{t("history:empty.title")}</TrackedLabel>
      <p style={EMPTY_BODY_STYLE} data-testid="history-empty-body">
        {t("history:empty.body")}
      </p>
      <SolidCTA
        onClick={handleNewChat}
        aria-label={t("history:empty.cta")}
        data-testid="history-empty-cta"
      >
        {t("history:empty.cta")}
      </SolidCTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NetworkErrorView
// ---------------------------------------------------------------------------

export interface NetworkErrorViewProps {
  onRetry: () => void;
  loading: boolean;
}

/**
 * Network error state — shown on 5xx or fetch failure.
 * Provides retry CTA that triggers query.refetch().
 */
export function NetworkErrorView({ onRetry, loading }: NetworkErrorViewProps): ReactNode {
  const { t } = useTranslation(["history"]);
  return (
    <div
      role="status"
      aria-live="assertive"
      data-testid="history-network-error"
      style={ERROR_CONTAINER_STYLE}
    >
      <p style={ERROR_TEXT_STYLE}>{t("history:errorNetwork.title")}</p>
      <SolidCTA
        onClick={onRetry}
        loading={loading}
        loadingLabel="…"
        aria-label={t("history:errorNetwork.retry")}
        data-testid="history-retry-cta"
      >
        {t("history:errorNetwork.retry")}
      </SolidCTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ForbiddenView
// ---------------------------------------------------------------------------

/**
 * Permission denied state — defensive 403 path.
 * For 401 final, RequireAuth already redirects — this handles 403 only.
 */
export function ForbiddenView(): ReactNode {
  const { t } = useTranslation(["history"]);
  return (
    <div
      role="status"
      aria-live="assertive"
      data-testid="history-forbidden"
      style={ERROR_CONTAINER_STYLE}
    >
      <p style={ERROR_TEXT_STYLE}>{t("history:permissionDenied")}</p>
    </div>
  );
}

/**
 * Hilo People — HistoryPage.
 *
 * Slice/Phase: P03-S02-T003 — HistoryPage / Phase 3.
 *
 * Responsibility: Employee conversation history page (/history).
 *   Renders the 5 required UX states: loading, empty, error_network,
 *   permission_denied, success (grouped list by relative date).
 *   error_validation is N/A — no form input on this read-only page.
 *
 * §D-T003-PAGE — thin orchestrator: delegates data to useHistory hook,
 *   grouping to historyGrouping pure function. Sub-view components extracted to
 *   _HistoryPage.error-views.tsx (§D-T003-PAGE-SPLIT-ERRORVIEWS) due to file-size cap.
 *
 * Decisions:
 *   D-T003-FIRST-PAGE-ONLY: loads first page only; no infinite scroll in v1.
 *   D-T003-UNTITLED-FALLBACK: title null/empty → i18n key history.untitledConversation.
 *   D-T003-ROW-AS-BUTTON: each row is a <button> with accessible name including title.
 *   D-T003-CHEVRON-TEXT: chevron affordance as "›" character (no PNG icon, hairline grammar).
 *
 * Security:
 *   - Token NEVER in logs. PII-clean: no titles, no IDs in logs.
 *   - Uses useAuth().logout for auth-failure path.
 *
 * Route: /history (RequireAuth — authenticated employee only).
 * Journey refs: J102 (participates; does NOT close — terminal is P05-S01-T003).
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR gated by VITE_ENABLE_VERBOSE_LOGGING.
 */

import { type CSSProperties, type ReactNode, useCallback, useEffect } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import MobileFrame from "../../shared/design-system/MobileFrame";
import TrackedLabel from "../../shared/design-system/TrackedLabel";
import { useAuth } from "../../features/auth/presentation/AuthProvider";
import { useHistory } from "../../features/chat/presentation/useHistory";
import { groupConversationsByRelativeDate } from "../../features/chat/presentation/historyGrouping";
import { ChatForbiddenError } from "../../features/chat/data/errors";
import { logVerbose, logWarn } from "../../features/chat/data/logger";
import type { ConversationSummary } from "../../features/chat/domain/types";
import type { GroupKey } from "../../features/chat/presentation/historyGrouping";
import {
  LoadingSkeleton,
  EmptyState,
  NetworkErrorView,
  ForbiddenView,
} from "./_HistoryPage.error-views";

// ---------------------------------------------------------------------------
// Styles (tokens only — no hardcoded colors, radii, or shadows)
// ---------------------------------------------------------------------------

const PAGE_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
};

const GROUP_LABEL_STYLE: CSSProperties = {
  paddingTop: "1.25rem",
  paddingBottom: "0.5rem",
};

const HAIRLINE_STYLE: CSSProperties = {
  border: "none",
  borderTop: "var(--hairline)",
  margin: 0,
};

const ROW_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  width: "100%",
  padding: "0.875rem 0",
  background: "none",
  border: "none",
  borderBottom: "var(--hairline)",
  cursor: "pointer",
  textAlign: "left",
  fontFamily: "var(--font-sans)",
  color: "var(--color-ink)",
};

const ROW_TITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.9375rem",
  color: "var(--color-ink)",
  flex: 1,
};

const ROW_CHEVRON_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "1.125rem",
  color: "var(--color-ink)",
  opacity: 0.5,
  marginLeft: "0.75rem",
  flexShrink: 0,
};

// ---------------------------------------------------------------------------
// ConversationRow
// ---------------------------------------------------------------------------

interface ConversationRowProps {
  conv: ConversationSummary;
  onOpen: (id: string, title: string) => void;
}

/**
 * A single conversation row button with keyboard navigation support.
 * Accessible name: "Open conversation, {{title}}".
 */
function ConversationRow({ conv, onOpen }: ConversationRowProps): ReactNode {
  const { t } = useTranslation(["history"]);
  const displayTitle = conv.title || t("history:untitledConversation");
  const label = t("history:row.openLabel", { title: displayTitle });

  const handleClick = useCallback((): void => {
    onOpen(conv.id, displayTitle);
  }, [conv.id, displayTitle, onOpen]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent): void => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onOpen(conv.id, displayTitle);
      }
    },
    [conv.id, displayTitle, onOpen],
  );

  return (
    <button
      type="button"
      style={ROW_STYLE}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      aria-label={label}
      data-testid={`history-row-${conv.id}`}
    >
      <span style={ROW_TITLE_STYLE}>{displayTitle}</span>
      <span style={ROW_CHEVRON_STYLE} aria-hidden="true">›</span>
    </button>
  );
}

/** Maps group key to i18n translation key. */
function groupLabel(key: GroupKey): string {
  const map: Record<GroupKey, string> = {
    today: "history:groups.today",
    yesterday: "history:groups.yesterday",
    thisWeek: "history:groups.thisWeek",
    thisMonth: "history:groups.thisMonth",
    earlier: "history:groups.earlier",
  };
  return map[key];
}

// ---------------------------------------------------------------------------
// HistoryPage
// ---------------------------------------------------------------------------

/**
 * Employee conversation history page — lists past conversations grouped by date.
 *
 * @returns The history page element.
 */
export default function HistoryPage(): ReactNode {
  const { t } = useTranslation(["history"]);
  const navigate = useNavigate();
  const { logout } = useAuth();

  const handleAuthFailure = useCallback((): void => {
    logWarn("chat.history.page.auth_failure_triggered");
    void logout();
  }, [logout]);

  const { data, isPending, isError, error, refetch, isFetching } =
    useHistory(handleAuthFailure);

  const isForbidden = isError && error instanceof ChatForbiddenError;
  const isNetworkError = isError && !isForbidden;
  const conversations = data?.data ?? [];
  const groups = groupConversationsByRelativeDate(conversations, new Date());

  // BEFORE/AFTER render log
  useEffect(() => {
    const phase = isPending
      ? "loading"
      : isForbidden
        ? "permission_denied"
        : isNetworkError
          ? "error_network"
          : conversations.length === 0
            ? "empty"
            : "success";

    logVerbose("chat.history.page.render", {
      phase,
      count: conversations.length,
    });
  });

  const handleOpenConversation = useCallback(
    (id: string, title: string): void => {
      logVerbose("chat.history.page.row_click", { title_len: title.length });
      void navigate(`/chat/${id}`);
    },
    [navigate],
  );

  const handleRetry = useCallback((): void => {
    logVerbose("chat.history.page.retry");
    void refetch();
  }, [refetch]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <MobileFrame asMain>
      <div
        style={PAGE_STYLE}
        data-testid="history-page"
      >
        <TrackedLabel as="h1">{t("history:pageTitle")}</TrackedLabel>

        {/* loading state */}
        {isPending && <LoadingSkeleton />}

        {/* permission_denied state (403) — defensive */}
        {isForbidden && <ForbiddenView />}

        {/* error_network state (5xx / fetch failure) */}
        {isNetworkError && (
          <NetworkErrorView
            onRetry={handleRetry}
            loading={isFetching}
          />
        )}

        {/* empty state — no conversations yet */}
        {!isPending && !isError && conversations.length === 0 && (
          <EmptyState />
        )}

        {/* success state — grouped list */}
        {!isPending && !isError && conversations.length > 0 && (
          <nav aria-label={t("history:list.aria")}>
            {groups.map((group) => (
              <section key={group.key}>
                <hr style={HAIRLINE_STYLE} />
                <div style={GROUP_LABEL_STYLE}>
                  <TrackedLabel>{t(groupLabel(group.key))}</TrackedLabel>
                </div>
                {group.items.map((conv) => (
                  <ConversationRow
                    key={conv.id}
                    conv={conv}
                    onOpen={handleOpenConversation}
                  />
                ))}
              </section>
            ))}
          </nav>
        )}
      </div>
    </MobileFrame>
  );
}

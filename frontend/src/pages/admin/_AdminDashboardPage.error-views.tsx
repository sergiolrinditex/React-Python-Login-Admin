/**
 * Hilo People — AdminDashboardPage error/empty sub-views.
 *
 * Slice/Phase: P04-S01-T001 — AdminDashboardPage / Phase 4.
 * Write-set anchor: §D-T001-FILESIZE-SPLIT
 *
 * Responsibility: Isolates the loading-skeleton, empty, error_network, and
 *   permission_denied sub-views from AdminDashboardPage.tsx to keep the main
 *   file within the ~300-line file-size cap (T002/T003/T004 precedent).
 *
 * Consumers: AdminDashboardPage.tsx only.
 * Design: token-only styles (no hardcoded literals). No border-radius.
 * Accessibility: roles/aria-labels per UX_CONTRACT /admin row requirements.
 */

import type { CSSProperties, ReactNode } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import Wordmark from "../../shared/design-system/Wordmark";
import SolidCTA from "../../shared/design-system/SolidCTA";
import TrackedLabel from "../../shared/design-system/TrackedLabel";
import { ROUTE_ADMIN_AI_MODELS } from "../../app/router";

// ---------------------------------------------------------------------------
// Shared styles (token-only)
// ---------------------------------------------------------------------------

const CENTER_BLOCK: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "flex-start",
  gap: "1.25rem",
  maxWidth: "480px",
};

const BODY_TEXT: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.9375rem",
  color: "var(--color-ink)",
  opacity: 0.75,
  lineHeight: 1.6,
  margin: 0,
};

const SKELETON_ROW: CSSProperties = {
  height: "1rem",
  backgroundColor: "var(--color-ink)",
  opacity: 0.06,
  marginBottom: "0.5rem",
};

const SKELETON_TILE: CSSProperties = {
  height: "80px",
  backgroundColor: "var(--color-ink)",
  opacity: 0.06,
  border: "var(--hairline)",
};

// ---------------------------------------------------------------------------
// LoadingView — aria-busy skeleton
// ---------------------------------------------------------------------------

/**
 * Loading skeleton — shown while the query is in-flight.
 * Uses aria-busy="true" on the region. No spinner per D-T001-UX-STATES.
 */
export function LoadingView(): ReactNode {
  const { t } = useTranslation(["admin-ai"]);
  return (
    <div
      aria-busy="true"
      aria-label={t("admin-ai:dashboard.title")}
      role="status"
      data-testid="admin-dashboard-loading"
    >
      {/* KPI skeleton tiles */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "1rem",
          marginBottom: "2rem",
        }}
      >
        {[0, 1, 2, 3].map((i) => (
          <div key={i} style={SKELETON_TILE} aria-hidden="true" />
        ))}
      </div>
      {/* Table skeleton rows */}
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          style={{ ...SKELETON_ROW, width: i % 2 === 0 ? "80%" : "60%" }}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// EmptyView — no usage yet
// ---------------------------------------------------------------------------

/**
 * Empty state — 200 OK with rows=[] and totals.invocations=0.
 * Shows Wordmark + body + manageModels CTA per D-T001-UX-STATES.
 */
export function EmptyView(): ReactNode {
  const { t } = useTranslation(["admin-ai"]);
  const navigate = useNavigate();

  return (
    <div
      style={CENTER_BLOCK}
      role="status"
      aria-live="polite"
      data-testid="admin-dashboard-empty"
    >
      <Wordmark size="2rem" aria-label="Hilo" />
      <TrackedLabel as="h2" variant="default" data-testid="empty-title">
        {t("admin-ai:dashboard.empty.title")}
      </TrackedLabel>
      <p style={BODY_TEXT} data-testid="empty-body">
        {t("admin-ai:dashboard.empty.body")}
      </p>
      <SolidCTA
        onClick={() => navigate(ROUTE_ADMIN_AI_MODELS)}
        aria-label={t("admin-ai:dashboard.actions.manageModels")}
        data-testid="empty-manage-models-cta"
        width="auto"
        style={{ padding: "0.75rem 1.5rem" }}
      >
        {t("admin-ai:dashboard.actions.manageModels")}
      </SolidCTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NetworkErrorView — error_network state
// ---------------------------------------------------------------------------

interface NetworkErrorViewProps {
  onRetry: () => void;
}

/**
 * Network error view — shown for transient errors or 5xx responses.
 * Provides a retry CTA that calls useQuery.refetch().
 */
export function NetworkErrorView({ onRetry }: NetworkErrorViewProps): ReactNode {
  const { t } = useTranslation(["admin-ai"]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      style={CENTER_BLOCK}
      data-testid="admin-dashboard-error-network"
    >
      <TrackedLabel as="h2" variant="default" data-testid="error-network-title">
        {t("admin-ai:dashboard.errors.network.title")}
      </TrackedLabel>
      <p style={BODY_TEXT} data-testid="error-network-body">
        {t("admin-ai:dashboard.errors.network.body")}
      </p>
      <SolidCTA
        onClick={onRetry}
        aria-label={t("admin-ai:dashboard.actions.retry")}
        data-testid="error-network-retry-cta"
        width="auto"
        style={{ padding: "0.75rem 1.5rem" }}
      >
        {t("admin-ai:dashboard.actions.retry")}
      </SolidCTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ForbiddenView — permission_denied state
// ---------------------------------------------------------------------------

/**
 * Forbidden view — defensive 403 state.
 * In practice RequireRole prevents reaching the fetch for non-admins;
 * this renders when the API returns 403 anyway.
 */
export function ForbiddenView(): ReactNode {
  const { t } = useTranslation(["admin-ai"]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      style={CENTER_BLOCK}
      data-testid="admin-dashboard-forbidden"
    >
      <TrackedLabel as="h2" variant="default" data-testid="forbidden-title">
        {t("admin-ai:dashboard.errors.forbidden.title")}
      </TrackedLabel>
      <p style={BODY_TEXT} data-testid="forbidden-body">
        {t("admin-ai:dashboard.errors.forbidden.body")}
      </p>
    </div>
  );
}

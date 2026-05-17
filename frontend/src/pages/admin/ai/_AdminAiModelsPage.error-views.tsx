/**
 * Hilo People — AdminAiModelsPage error/empty/loading sub-views.
 *
 * Slice/Phase: P04-S01-T002 — AdminAiModelsPage / Phase 4.
 * Write-set anchor: §D-T002-FILESIZE-SPLIT-ERRORVIEWS
 *
 * Responsibility: Isolates the loading-skeleton, empty, error_network, and
 *   permission_denied sub-views from AdminAiModelsPage.tsx to keep the main
 *   file within the ~300-line file-size cap (mirrors _AdminDashboardPage.error-views.tsx).
 *
 * Consumers: AdminAiModelsPage.tsx only.
 * Design: token-only styles (no hardcoded literals). No border-radius (§3.7).
 * Accessibility: roles/aria-labels per UX_CONTRACT §7 / §D-T002-ACCESSIBILITY.
 *
 * Non-negotiables: no PII in logs, VITE_ENABLE_VERBOSE_LOGGING gating.
 */

import type { CSSProperties, ReactNode } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import Wordmark from "../../../shared/design-system/Wordmark";
import SolidCTA from "../../../shared/design-system/SolidCTA";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import { ROUTE_ADMIN_AI_MODELS_NEW } from "../../../app/router";

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

const SKELETON_HEADER: CSSProperties = {
  height: "1.25rem",
  backgroundColor: "var(--color-ink)",
  opacity: 0.09,
  marginBottom: "1rem",
};

// ---------------------------------------------------------------------------
// LoadingView — aria-busy skeleton
// ---------------------------------------------------------------------------

/**
 * Loading skeleton — shown while the query is in-flight.
 * Uses aria-busy="true" on the region. Respects prefers-reduced-motion (no animation).
 * Source: D-T002-UX-STATES, §D-T002-ACCESSIBILITY.
 */
export function LoadingView(): ReactNode {
  const { t } = useTranslation(["admin-ai"]);
  return (
    <div
      aria-busy="true"
      aria-label={t("admin-ai:models.title")}
      role="status"
      aria-live="polite"
      data-testid="admin-ai-models-loading"
    >
      {/* Table header skeleton */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "1rem", marginBottom: "1rem" }}>
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} style={SKELETON_HEADER} aria-hidden="true" />
        ))}
      </div>
      {/* Table row skeletons */}
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{ ...SKELETON_ROW, width: i % 2 === 0 ? "90%" : "70%" }}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// EmptyView — no providers/models yet (D-T002-EMPTY-STATE)
// ---------------------------------------------------------------------------

/**
 * Empty state — providers=[] OR models=[].
 * Full-bleed Wordmark + body + Create-model CTA per D-T002-EMPTY-STATE.
 * The CTA navigates to ROUTE_ADMIN_AI_MODELS_NEW (T003 future page).
 *
 * Source: §6.7 D-T002-EMPTY-STATE, D-T002-NEXT-ACTION.
 */
export function EmptyView(): ReactNode {
  const { t } = useTranslation(["admin-ai"]);
  const navigate = useNavigate();

  return (
    <div
      style={CENTER_BLOCK}
      role="status"
      aria-live="polite"
      data-testid="admin-ai-models-empty"
    >
      <Wordmark size="2rem" aria-label="Hilo" />
      <TrackedLabel as="h2" variant="default" data-testid="models-empty-heading">
        {t("admin-ai:models.title")}
      </TrackedLabel>
      <p style={BODY_TEXT} data-testid="models-empty-body">
        {t("admin-ai:models.empty.body")}
      </p>
      <SolidCTA
        onClick={() => navigate(ROUTE_ADMIN_AI_MODELS_NEW)}
        aria-label={t("admin-ai:models.empty.cta")}
        data-testid="models-empty-new-model-cta"
        width="auto"
        style={{ padding: "0.75rem 1.5rem", minHeight: "44px" }}
      >
        {t("admin-ai:models.empty.cta")}
      </SolidCTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NetworkErrorView — error_network state (D-T002-ERROR-NETWORK)
// ---------------------------------------------------------------------------

interface NetworkErrorViewProps {
  /** Retry callback — calls useQuery.refetch() (D-T002-RETRY-INVALIDATES). */
  onRetry: () => void;
}

/**
 * Network error view — shown for AdminAiNetworkError + AdminAiInternalError (5xx).
 * Provides a retry CTA with tap target ≥ 44px (§D-T002-ACCESSIBILITY).
 *
 * Source: §6.9 D-T002-ERROR-NETWORK.
 */
export function NetworkErrorView({ onRetry }: NetworkErrorViewProps): ReactNode {
  const { t } = useTranslation(["admin-ai"]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      style={CENTER_BLOCK}
      data-testid="admin-ai-models-error-network"
    >
      <TrackedLabel as="h2" variant="default" data-testid="models-error-network-title">
        {t("admin-ai:models.errors.network.title")}
      </TrackedLabel>
      <p style={BODY_TEXT} data-testid="models-error-network-body">
        {t("admin-ai:models.errors.network.body")}
      </p>
      <SolidCTA
        onClick={onRetry}
        aria-label={t("admin-ai:models.actions.retry")}
        data-testid="models-error-network-retry-cta"
        width="auto"
        style={{ padding: "0.75rem 1.5rem", minHeight: "44px" }}
      >
        {t("admin-ai:models.actions.retry")}
      </SolidCTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ForbiddenView — permission_denied state (D-T002-PERMISSION-DENIED)
// ---------------------------------------------------------------------------

/**
 * Forbidden view — defensive 403 state.
 * In practice RequireRole prevents non-admins; this view renders if the API
 * returns 403 despite the route guard (race / session downgrade).
 *
 * Source: §6.8 D-T002-PERMISSION-DENIED.
 */
export function ForbiddenView(): ReactNode {
  const { t } = useTranslation(["admin-ai"]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      style={CENTER_BLOCK}
      data-testid="admin-ai-models-forbidden"
    >
      <TrackedLabel as="h2" variant="default" data-testid="models-forbidden-title">
        {t("admin-ai:models.errors.forbidden.title")}
      </TrackedLabel>
      <p style={BODY_TEXT} data-testid="models-forbidden-body">
        {t("admin-ai:models.errors.forbidden.body")}
      </p>
    </div>
  );
}

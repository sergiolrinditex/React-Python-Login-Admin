/**
 * Hilo People — AgentsPage error-state views.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: Extracted error/loading/empty view components for AgentsPage.
 *   LoadingSkeletonView, EmptyView, NetworkErrorView, ForbiddenView.
 *   Extracted to keep AgentsPage.tsx within the ~300-line cap.
 *
 * §D-T005-PAGE-SPLIT-ERRORVIEWS (P04-S02-T005 task pack §8.3)
 *
 * Note: these are NOT imported from _RagDocumentsPage.error-views.tsx (separate
 * folder, different copy / different i18n keys). P-44 #6 DRY only applies within
 * the same folder feature.
 *
 * a11y: aria-busy for loading; role="alert" from HairlineTable for error states.
 */

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import HairlineTable from "../../../shared/design-system/HairlineTable";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import Wordmark from "../../../shared/design-system/Wordmark";
import { LOADING_STYLE, EMPTY_BODY_STYLE } from "./AgentsPage.styles";

// ---------------------------------------------------------------------------
// LoadingSkeletonView
// ---------------------------------------------------------------------------

/**
 * Loading skeleton for the agents table.
 * Renders aria-busy section with sr-only caption.
 */
export function LoadingSkeletonView(): ReactNode {
  const { t } = useTranslation("agents");

  return (
    <div
      aria-busy="true"
      aria-label={t("title")}
      data-testid="agents-loading"
      style={LOADING_STYLE}
    >
      <TrackedLabel variant="muted">Cargando…</TrackedLabel>
    </div>
  );
}

// ---------------------------------------------------------------------------
// EmptyView
// ---------------------------------------------------------------------------

/**
 * Empty state for the agents table.
 * §D-T005-EMPTY-STATE: Wordmark + body paragraph + NO CTA (admin v1 has no "create agent").
 * Agents are seeded by verification_data / migrations only.
 */
export function EmptyView(): ReactNode {
  const { t } = useTranslation("agents");

  return (
    <div data-testid="agents-empty">
      <HairlineTable
        columns={[]}
        rows={[]}
        state="empty"
        caption={t("title")}
        emptyMessage={t("empty")}
      />
      {/* §D-T005-EMPTY-STATE: no CTA — agents not user-created in v1 */}
      <div style={EMPTY_BODY_STYLE} data-testid="agents-empty-body">
        <Wordmark size="1.25rem" />
        <p style={{ margin: "0.5rem 0 0" }}>{t("empty.body")}</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NetworkErrorView
// ---------------------------------------------------------------------------

/**
 * Network error state for the agents table.
 * Renders HairlineTable state="error_network" with retry button.
 */
export function NetworkErrorView({ onRetry }: { onRetry: () => void }): ReactNode {
  const { t: tErrors } = useTranslation("errors");
  const { t } = useTranslation("agents");

  return (
    <HairlineTable
      columns={[]}
      rows={[]}
      state="error_network"
      caption={t("title")}
      errorMessage={tErrors("NETWORK")}
      onRetry={onRetry}
    />
  );
}

// ---------------------------------------------------------------------------
// ForbiddenView
// ---------------------------------------------------------------------------

/**
 * Permission denied state for the agents table.
 * Renders HairlineTable state="permission_denied".
 */
export function ForbiddenView(): ReactNode {
  const { t } = useTranslation("agents");

  return (
    <HairlineTable
      columns={[]}
      rows={[]}
      state="permission_denied"
      caption={t("title")}
    />
  );
}

/**
 * Hilo People — UsagePage error sub-views.
 *
 * Slice/Phase: P04-S03-T002 — UsagePage / Phase 4 Complete Features.
 *
 * Responsibility: Isolated error and empty state sub-components for UsagePage.
 *   Split from UsagePage.tsx to stay within the 300 LoC cap.
 *   Renders: LoadingView, EmptyView, ForbiddenView, NetworkErrorView, ValidationErrorView.
 *
 * All components:
 *   - Use i18n keys from the "usage" namespace (lockstep ES/EN/FR).
 *   - Use tokens.css custom properties — NO hardcoded colors/fonts.
 *   - Follow D-T002-TABLE-A11Y: role=status + aria-live for dynamic content.
 *
 * D-T002-PAGE-SPLIT-ERRORVIEWS: Conditional write_set anchor for this file.
 * Source ref: §D-T002-PAGE-SPLIT-ERRORVIEWS, task pack §10 allowed_paths.
 */

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import {
  SKELETON_STYLE,
  SKELETON_ROW_STYLE,
  EMPTY_STYLE,
  EMPTY_WORDMARK_STYLE,
  BODY_TEXT_STYLE,
  LINK_CTA_STYLE,
  ERROR_CONTAINER_STYLE,
  SOLID_BTN_STYLE,
} from "./UsagePage.styles";

// ---------------------------------------------------------------------------
// LoadingView
// ---------------------------------------------------------------------------

/**
 * loading state — skeleton table rows with aria-busy.
 * Shown while useQuery isPending and range is valid.
 */
export function LoadingView(): ReactNode {
  const { t } = useTranslation("usage");
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label={t("loading")}
      data-testid="usage-loading"
      style={SKELETON_STYLE}
    >
      {/* Simulate 6 skeleton rows */}
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} style={SKELETON_ROW_STYLE} aria-hidden="true" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// EmptyView
// ---------------------------------------------------------------------------

/**
 * empty state — Wordmark + body + CTA to /admin/ai/models.
 * Shown when success && rows.length === 0 (D-T002-EMPTY-STATE).
 * Next action per D-T002-NEXT-ACTION: link to /admin/ai/models.
 */
export function EmptyView(): ReactNode {
  const { t } = useTranslation("usage");
  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="usage-empty"
      style={EMPTY_STYLE}
    >
      <p style={EMPTY_WORDMARK_STYLE}>Hilo</p>
      <p style={BODY_TEXT_STYLE}>{t("empty.body")}</p>
      <Link
        to="/admin/ai/models"
        style={LINK_CTA_STYLE}
        data-testid="usage-empty-cta"
      >
        {t("empty.cta")}
      </Link>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ForbiddenView
// ---------------------------------------------------------------------------

interface ForbiddenViewProps {
  /** Called when back/retry button is clicked. */
  onBack: () => void;
}

/**
 * permission_denied state — 403 from backend.
 * For 401 final, RequireAuth already redirects — this handles 403.
 */
export function ForbiddenView({ onBack }: ForbiddenViewProps): ReactNode {
  const { t } = useTranslation(["usage", "common"]);
  return (
    <div
      role="status"
      aria-live="assertive"
      data-testid="usage-forbidden"
      style={ERROR_CONTAINER_STYLE}
    >
      <p style={BODY_TEXT_STYLE}>{t("usage:errors.forbidden.body")}</p>
      <button
        type="button"
        onClick={onBack}
        style={SOLID_BTN_STYLE}
        aria-label={t("common:actions.back")}
        data-testid="usage-forbidden-back"
      >
        {t("common:actions.back")}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NetworkErrorView
// ---------------------------------------------------------------------------

interface NetworkErrorViewProps {
  /** Called when Retry CTA is clicked. */
  onRetry: () => void;
  /** True while re-fetch is in progress (disables button). */
  loading: boolean;
}

/**
 * error_network state — 5xx or fetch failure.
 * Provides Retry CTA per D-T002-ERROR-MAPPING.
 */
export function NetworkErrorView({ onRetry, loading }: NetworkErrorViewProps): ReactNode {
  const { t } = useTranslation(["usage", "common"]);
  return (
    <div
      role="status"
      aria-live="assertive"
      data-testid="usage-network-error"
      style={ERROR_CONTAINER_STYLE}
    >
      <p style={BODY_TEXT_STYLE}>{t("usage:errors.network")}</p>
      <button
        type="button"
        onClick={onRetry}
        disabled={loading}
        style={SOLID_BTN_STYLE}
        aria-label={t("usage:errors.network.retry")}
        data-testid="usage-retry-cta"
      >
        {loading ? "…" : t("usage:errors.network.retry")}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ValidationErrorView
// ---------------------------------------------------------------------------

/**
 * error_validation state — client-side range invariant failed.
 * No fetch is triggered (D-T002-RANGE-INVARIANT); shown inline.
 */
export function ValidationErrorView(): ReactNode {
  const { t } = useTranslation("usage");
  return (
    <div
      role="alert"
      data-testid="usage-validation-error"
      style={ERROR_CONTAINER_STYLE}
    >
      <p style={BODY_TEXT_STYLE}>{t("errors.validation.range")}</p>
    </div>
  );
}

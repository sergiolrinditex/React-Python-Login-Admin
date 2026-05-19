/**
 * Hilo People — AuditLogPage error sub-views.
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: Isolated error and empty state sub-components for AuditLogPage.
 *   Split from AuditLogPage.tsx to stay within the 300 LoC cap.
 *   Renders: LoadingView, EmptyView, ForbiddenView, NetworkErrorView, ValidationErrorView.
 *
 * All components:
 *   - Use i18n keys from the "audit" namespace (lockstep ES/EN/FR).
 *   - Use tokens.css custom properties — NO hardcoded colors/fonts.
 *   - Follow D-T001-A11Y: role=status + aria-live for dynamic content.
 *
 * §D-T001-PAGE: Conditional write_set anchor for this file.
 * Source ref: §D-T001-PAGE, task pack §6 allowed_paths.
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
  VALIDATION_MSG_STYLE,
} from "./AuditLogPage.styles";

// ---------------------------------------------------------------------------
// LoadingView
// ---------------------------------------------------------------------------

/**
 * loading state — skeleton rows with aria-busy.
 * Shown while useQuery isPending and filters are valid.
 */
export function LoadingView(): ReactNode {
  const { t } = useTranslation("audit");
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label={t("loading")}
      data-testid="audit-loading"
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
 * empty state — Wordmark + body + CTA to dashboard.
 * Shown when success && rows.length === 0.
 * D-T001-EMPTY-STATE: no audit events in the current window.
 */
export function EmptyView(): ReactNode {
  const { t } = useTranslation("audit");
  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="audit-empty"
      style={EMPTY_STYLE}
    >
      <p style={EMPTY_WORDMARK_STYLE}>Hilo</p>
      <p style={BODY_TEXT_STYLE}>{t("empty.body")}</p>
      <Link
        to="/admin"
        style={LINK_CTA_STYLE}
        data-testid="audit-empty-cta"
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
  /** Called when back button is clicked. */
  onBack: () => void;
}

/**
 * permission_denied state — 403 from backend.
 * For 401 final, RequireAuth already redirects — this handles 403.
 * Note: with RequireRole guard, this is a defensive state for mid-session role loss.
 */
export function ForbiddenView({ onBack }: ForbiddenViewProps): ReactNode {
  const { t } = useTranslation(["audit", "common"]);
  return (
    <div
      role="status"
      aria-live="assertive"
      data-testid="audit-forbidden"
      style={ERROR_CONTAINER_STYLE}
    >
      <p style={BODY_TEXT_STYLE}>{t("audit:errors.forbidden.body")}</p>
      <button
        type="button"
        onClick={onBack}
        style={SOLID_BTN_STYLE}
        aria-label={t("common:actions.back")}
        data-testid="audit-forbidden-back"
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
 * Provides Retry CTA per D-T001-ERROR-MAPPING.
 */
export function NetworkErrorView({ onRetry, loading }: NetworkErrorViewProps): ReactNode {
  const { t } = useTranslation("audit");
  return (
    <div
      role="status"
      aria-live="assertive"
      data-testid="audit-network-error"
      style={ERROR_CONTAINER_STYLE}
    >
      <p style={BODY_TEXT_STYLE}>{t("errors.network")}</p>
      <button
        type="button"
        onClick={onRetry}
        disabled={loading}
        style={SOLID_BTN_STYLE}
        aria-label={t("errors.network.retry")}
        data-testid="audit-retry-cta"
      >
        {loading ? "…" : t("errors.network.retry")}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ValidationErrorView
// ---------------------------------------------------------------------------

interface ValidationErrorViewProps {
  /** Specific validation error sub-code for localized message. */
  subCode?: "range" | "window" | "actor";
}

/**
 * error_validation state — client-side filter validation failed.
 * No fetch is triggered; shown inline above the filter bar.
 * D-T001-RANGE-INVARIANT: range or actor validation prevents the fetch.
 */
export function ValidationErrorView({ subCode }: ValidationErrorViewProps): ReactNode {
  const { t } = useTranslation("audit");
  const msgKey = subCode === "actor"
    ? "errors.validation.actor"
    : subCode === "window"
      ? "errors.validation.window"
      : "errors.validation.range";

  return (
    <div
      role="alert"
      data-testid="audit-validation-error"
      style={ERROR_CONTAINER_STYLE}
    >
      <p style={VALIDATION_MSG_STYLE}>{t(msgKey)}</p>
    </div>
  );
}

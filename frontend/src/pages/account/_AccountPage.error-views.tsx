/**
 * Hilo People — AccountPage error/state sub-views.
 *
 * Slice/Phase: P03-S02-T007 — AccountPage (profile + language + logout) / Phase 3.
 *
 * Responsibility: LoadingSkeleton, NetworkErrorView, ValidationErrorView, PermissionDeniedView
 *   sub-components for AccountPage. Extracted to honor file-size cap (~300 lines).
 *   Pre-authorized pattern (§D-T003-PAGE-SPLIT-ERRORVIEWS, §D-T007-R7-PREAUTHORIZED-SPLIT).
 *
 * Non-negotiables §logging: callers (AccountPage) log; these are pure presentation sub-components.
 * Design tokens: ONLY from tokens.css. No hardcoded hex/px/font-family.
 * Accessibility: aria-busy, aria-live, role="status" on all dynamic states.
 *
 * Key deps: react-i18next (useTranslation), design-system (SolidCTA, TrackedLabel).
 */

import { type CSSProperties, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import SolidCTA from "../../shared/design-system/SolidCTA";

// ---------------------------------------------------------------------------
// Shared styles (tokens only)
// ---------------------------------------------------------------------------

const STATE_CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
  paddingTop: "2rem",
  paddingBottom: "1rem",
};

const STATE_TITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.9375rem",
  fontWeight: 600,
  color: "var(--color-ink)",
  margin: 0,
};

const STATE_BODY_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.85,
  margin: 0,
};

const LOADING_CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.75rem",
  paddingTop: "1.25rem",
};

const SKELETON_BLOCK_STYLE: CSSProperties = {
  height: "1.5rem",
  background: "var(--color-paper)",
  borderBottom: "var(--hairline)",
  width: "100%",
  opacity: 0.6,
};

const SKELETON_BLOCK_WIDE_STYLE: CSSProperties = {
  ...SKELETON_BLOCK_STYLE,
  width: "70%",
};

// ---------------------------------------------------------------------------
// LoadingSkeleton
// ---------------------------------------------------------------------------

/**
 * Loading state — aria-busy=true skeleton rows while profile loads.
 * Shown during initial AuthProvider hydration or refetch.
 */
export function LoadingSkeleton(): ReactNode {
  const { t } = useTranslation(["account"]);
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label={t("account:states.loading")}
      data-testid="account-loading"
      style={LOADING_CONTAINER_STYLE}
    >
      <div style={SKELETON_BLOCK_WIDE_STYLE} />
      <div style={SKELETON_BLOCK_STYLE} />
      <div style={SKELETON_BLOCK_WIDE_STYLE} />
      <div style={SKELETON_BLOCK_STYLE} />
      <div style={{ ...SKELETON_BLOCK_WIDE_STYLE, width: "50%" }} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// NetworkErrorView
// ---------------------------------------------------------------------------

export interface NetworkErrorViewProps {
  onRetry: () => void;
  loading?: boolean;
}

/**
 * Network error state — shown when GET /users/me fails with a network error.
 * Provides retry CTA that re-triggers the profile load.
 */
export function NetworkErrorView({ onRetry, loading = false }: NetworkErrorViewProps): ReactNode {
  const { t } = useTranslation(["account"]);
  return (
    <div
      role="status"
      aria-live="assertive"
      data-testid="account-network-error"
      style={STATE_CONTAINER_STYLE}
    >
      <p style={STATE_TITLE_STYLE}>{t("account:states.errorNetwork.title")}</p>
      <p style={STATE_BODY_STYLE}>{t("account:states.errorNetwork.body")}</p>
      <SolidCTA
        onClick={onRetry}
        loading={loading}
        loadingLabel="…"
        aria-label={t("account:states.errorNetwork.retry")}
        data-testid="account-retry-cta"
      >
        {t("account:states.errorNetwork.retry")}
      </SolidCTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ValidationErrorInline
// ---------------------------------------------------------------------------

/**
 * Inline validation error for language picker — shown when PATCH /me/language
 * returns 400/422. Renders inline near the picker, not as a full-page state.
 */
export function ValidationErrorInline(): ReactNode {
  const { t } = useTranslation(["account"]);
  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="account-validation-error"
      style={{ ...STATE_BODY_STYLE, color: "var(--color-ink)", opacity: 0.9 }}
    >
      {t("account:states.errorValidation.body")}
    </div>
  );
}

// ---------------------------------------------------------------------------
// PermissionDeniedView
// ---------------------------------------------------------------------------

/**
 * Permission denied state — shown when session expires and RequireAuth has not
 * yet redirected (transient window). Provides CTA to /auth/sign-in.
 *
 * In practice, RequireAuth handles the redirect before this renders.
 * This view is a defensive fallback for the brief moment between 401 + redirect.
 */
export function PermissionDeniedView({ onSignIn }: { onSignIn: () => void }): ReactNode {
  const { t } = useTranslation(["account"]);
  return (
    <div
      role="status"
      aria-live="assertive"
      data-testid="account-permission-denied"
      style={STATE_CONTAINER_STYLE}
    >
      <p style={STATE_TITLE_STYLE}>{t("account:states.permissionDenied.title")}</p>
      <p style={STATE_BODY_STYLE}>{t("account:states.permissionDenied.body")}</p>
      <SolidCTA
        onClick={onSignIn}
        aria-label={t("account:states.permissionDenied.cta")}
        data-testid="account-signin-cta"
      >
        {t("account:states.permissionDenied.cta")}
      </SolidCTA>
    </div>
  );
}

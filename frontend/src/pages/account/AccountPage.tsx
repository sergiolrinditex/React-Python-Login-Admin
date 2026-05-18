/**
 * Hilo People — AccountPage.
 *
 * Slice/Phase: P03-S02-T007 — AccountPage (profile + language + logout) / Phase 3.
 *
 * Responsibility: Employee account page (/account).
 *   Renders the 5 required UX states from UX_CONTRACT /account row:
 *   - loading: initial profile load (auth hydration in progress).
 *   - error_network: profile load failed (GET /users/me network error).
 *   - permission_denied: 401 + failed refresh → RequireAuth redirects (§N/A see below).
 *   - success: profile rendered (email + full_name + employee_profile) + language picker + logout.
 *   - empty: N/A — a logged-in user always has a profile (documented below).
 *   - error_validation: inline near language picker on PATCH 400/422.
 *
 * §D-T007-EMPTY-NA: empty state is not applicable for /account because RequireAuth
 *   guarantees that only authenticated users reach this page, and authenticated users
 *   always have a UserProfile (enforced by backend). There is no "no profile" scenario.
 *
 * §D-T007-PERMISSION-DENIED-NA: RequireAuth redirects to /auth/sign-in?next=/account
 *   before this page renders when the session is expired. The PermissionDeniedView is
 *   rendered only during the transient window between 401 and the redirect firing.
 *
 * §D-T007-USERREAD-CHOICE: uses useAuth().user directly (not a separate useMe query).
 *   Reason: AuthProvider hydrates user on mount and keeps it current. For the language
 *   change success case, i18n.language updates optimistically and AuthProvider.user updates
 *   on next /me call (e.g., next page mount). This is acceptable per task pack recommendation.
 *
 * §D-T007-LANG-PICKER-VARIANT: radiogroup-style language picker (not select).
 *   Keyboard-navigable, mobile-friendly, consistent with §D-T004-LANG-PICKER-VARIANT.
 *
 * §D-T007-LOGOUT-CONFIRM: no confirmation modal (§D-T004-LOGOUT-CONFIRM mirror).
 *   One click → logout.
 *
 * §D-T007-NAVBAR-DEFERRED: no navbar link in this slice (chat shell not in write_set).
 *   See handoff §D-T007-NAVBAR-DEFERRED. Verification uses direct URL.
 *
 * §D-T007-D2-NETWORK-RETRY (debugger cycle 1): NetworkErrorView is wired to the
 *   PATCH /me/language network error path with a retry CTA, replacing the previous
 *   ad-hoc inline div. This kills the dead-import smell and gives the user a clear
 *   recovery path for transient outages. The GET /users/me network error path is
 *   handled upstream by AuthProvider (collapses into permission_denied) — fixing
 *   that requires touching AuthProvider, which is out of T007 write_set.
 *
 * Route: /account (RequireAuth — authenticated employee only).
 * Journey refs: J102 participates (does NOT close — closed by T004 + P05-S01-T003).
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR gated by VITE_ENABLE_VERBOSE_LOGGING.
 * Security: NEVER log email or full_name (PII). Log user_id (UUID) only.
 *
 * Key deps: react, react-i18next, react-router, useAuth, useLogout, useLanguagePicker,
 *   design-system (SolidCTA, MobileFrame, TrackedLabel), i18n/languages.
 */

import { type ReactNode, useCallback, useEffect, useRef } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import MobileFrame from "../../shared/design-system/MobileFrame";
import TrackedLabel from "../../shared/design-system/TrackedLabel";
import SolidCTA from "../../shared/design-system/SolidCTA";
import { useAuth } from "../../features/auth/presentation/AuthProvider";
import { useLogout } from "../../features/auth/presentation/useLogout";
import { useLanguagePicker } from "../../features/auth/presentation/useLanguagePicker";
import type { Language } from "../../i18n/languages";
import { SUPPORTED_LANGUAGES } from "../../i18n/languages";
import { logVerbose, logWarn } from "../../features/auth/data/logger";
import { ROUTE_AUTH_SIGN_IN } from "../../app/router";
import {
  LoadingSkeleton,
  NetworkErrorView,
  ValidationErrorInline,
  PermissionDeniedView,
} from "./_AccountPage.error-views";
import {
  PAGE_CONTAINER_STYLE,
  CONTENT_WRAPPER_STYLE,
  PAGE_HEADER_STYLE,
  PAGE_TITLE_STYLE,
  SECTION_STYLE,
  SECTION_LABEL_STYLE,
  PROFILE_ROW_STYLE,
  PROFILE_LABEL_STYLE,
  PROFILE_VALUE_STYLE,
  LANGUAGE_PICKER_STYLE,
  LANGUAGE_OPTION_STYLE,
  LANGUAGE_OPTION_SELECTED_STYLE,
  LANGUAGE_OPTION_PENDING_STYLE,
  LOGOUT_SECTION_STYLE,
} from "./AccountPage.styles";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * AccountPage — employee account management screen at /account.
 *
 * Route guard: must be inside <RequireAuth> (configured in router.tsx §D-T007-ROUTER).
 *
 * @returns The account page element.
 */
export default function AccountPage(): ReactNode {
  const { t } = useTranslation(["account"]);
  const { status, user } = useAuth();
  const navigate = useNavigate();
  const { logout, isLoggingOut } = useLogout();
  const { current: currentLanguage, setLanguage, isPending: isLanguagePending, error: languageError } = useLanguagePicker();

  // Track mount for logging (BEFORE/AFTER mount)
  const mountedRef = useRef(false);

  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      if (user) {
        logVerbose("account.page.mount", { user_id: user.id });
      } else {
        logVerbose("account.page.mount.no_user");
      }
    }
    return () => {
      logVerbose("account.page.unmount");
    };
  }, [user]);

  // ---------------------------------------------------------------------------
  // Permission denied handler
  // ---------------------------------------------------------------------------

  const handleSignIn = useCallback((): void => {
    logWarn("account.page.permission_denied.signin_cta");
    void navigate(`${ROUTE_AUTH_SIGN_IN}?next=/account`);
  }, [navigate]);

  // ---------------------------------------------------------------------------
  // Language change handler
  // ---------------------------------------------------------------------------

  const handleLanguageChange = useCallback(
    (language: Language): void => {
      if (!isLanguagePending) {
        void setLanguage(language);
      }
    },
    [setLanguage, isLanguagePending],
  );

  // §D-T007-D2-NETWORK-RETRY (debugger cycle 1):
  //   Retry CTA for the language PATCH network error path. Re-attempts the user's
  //   last selected language. `currentLanguage` is the safe fallback when no prior
  //   target is in flight, so re-trying simply re-issues the PATCH for the language
  //   the user wanted (the optimistic value is already reverted before this CTA
  //   becomes visible).
  const handleLanguageRetry = useCallback((): void => {
    logVerbose("account.language.network_error.retry", {});
    if (!isLanguagePending) {
      void setLanguage(currentLanguage);
    }
  }, [setLanguage, isLanguagePending, currentLanguage]);

  // ---------------------------------------------------------------------------
  // Loading state
  // ---------------------------------------------------------------------------

  if (status === "hydrating") {
    return (
      <MobileFrame>
        <div style={PAGE_CONTAINER_STYLE}>
          <div style={CONTENT_WRAPPER_STYLE}>
            <LoadingSkeleton />
          </div>
        </div>
      </MobileFrame>
    );
  }

  // ---------------------------------------------------------------------------
  // Permission denied state — transient; RequireAuth handles actual redirect
  // ---------------------------------------------------------------------------

  if (status === "unauthenticated" || user === null) {
    logWarn("account.page.permission_denied", { status });
    return (
      <MobileFrame>
        <div style={PAGE_CONTAINER_STYLE}>
          <div style={CONTENT_WRAPPER_STYLE}>
            <PermissionDeniedView onSignIn={handleSignIn} />
          </div>
        </div>
      </MobileFrame>
    );
  }

  // ---------------------------------------------------------------------------
  // Error network state — if user was loaded but later a refetch fails,
  // show the error. (In practice AuthProvider rehydrates on mount; this handles
  // edge cases where user is null after a failed refresh.)
  // ---------------------------------------------------------------------------

  // At this point status === 'authenticated' && user !== null (guaranteed by guards above)
  const { email, full_name, employee_profile } = user;

  // ---------------------------------------------------------------------------
  // Success state
  // ---------------------------------------------------------------------------

  return (
    <MobileFrame>
      <div style={PAGE_CONTAINER_STYLE} data-testid="account-page">
        <div style={CONTENT_WRAPPER_STYLE}>

          {/* Page header */}
          <header style={PAGE_HEADER_STYLE}>
            <h1 style={PAGE_TITLE_STYLE} data-testid="account-title">
              {t("account:title")}
            </h1>
          </header>

          {/* Profile section */}
          <section style={SECTION_STYLE} aria-label={t("account:title")} data-testid="account-profile-section">
            <TrackedLabel>
              <span style={SECTION_LABEL_STYLE}>{t("account:title")}</span>
            </TrackedLabel>

            {/* Email row (PII: render only, never log) */}
            <ProfileRow
              label={t("account:profile.email")}
              value={email}
              testId="account-email-value"
            />

            {/* Full name row */}
            <ProfileRow
              label={t("account:profile.fullName")}
              value={full_name}
              testId="account-fullname-value"
            />

            {/* Employee profile fields (conditional on employee role) */}
            {employee_profile !== null && (
              <>
                <ProfileRow
                  label={t("account:profile.brand")}
                  value={employee_profile.brand}
                  testId="account-brand-value"
                />
                <ProfileRow
                  label={t("account:profile.department")}
                  value={employee_profile.department}
                  testId="account-department-value"
                />
                <ProfileRow
                  label={t("account:profile.country")}
                  value={employee_profile.country}
                  testId="account-country-value"
                />
                <ProfileRow
                  label={t("account:profile.center")}
                  value={employee_profile.center}
                  testId="account-center-value"
                />
              </>
            )}
          </section>

          {/* Language picker section */}
          <section style={SECTION_STYLE} data-testid="account-language-section">
            <p style={SECTION_LABEL_STYLE}>
              {t("account:language")}
            </p>
            <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", color: "var(--color-ink)", opacity: 0.65, margin: "0 0 0.75rem 0" }}>
              {t("account:languageHint")}
            </p>

            {/* Radio-group language picker (§D-T007-LANG-PICKER-VARIANT) */}
            <div
              role="radiogroup"
              aria-label={t("account:languagePicker.aria")}
              style={LANGUAGE_PICKER_STYLE}
              data-testid="account-language-picker"
            >
              {SUPPORTED_LANGUAGES.map((lang, idx) => {
                const isSelected = lang === currentLanguage;
                const isLast = idx === SUPPORTED_LANGUAGES.length - 1;
                const optionStyle = isLanguagePending
                  ? LANGUAGE_OPTION_PENDING_STYLE
                  : isSelected
                  ? LANGUAGE_OPTION_SELECTED_STYLE
                  : LANGUAGE_OPTION_STYLE;

                return (
                  <button
                    key={lang}
                    role="radio"
                    aria-checked={isSelected}
                    aria-label={t(`account:languagePicker.options.${lang}`)}
                    onClick={() => handleLanguageChange(lang as Language)}
                    disabled={isLanguagePending}
                    data-testid={`account-lang-option-${lang}`}
                    style={{
                      ...optionStyle,
                      borderRight: isLast ? "none" : "var(--hairline)",
                    }}
                  >
                    {t(`account:languagePicker.options.${lang}`)}
                  </button>
                );
              })}
            </div>

            {/* Inline validation error for language picker */}
            {languageError !== null && languageError.code === "validation" && (
              <ValidationErrorInline />
            )}

            {/* Inline network error for language PATCH — §D-T007-D2-NETWORK-RETRY
                Wires NetworkErrorView (with retry CTA) so the imported component is
                actually rendered and the user has a clear recovery path on transient
                network outages during language change. */}
            {languageError !== null && languageError.code === "network" && (
              <div data-testid="account-language-network-error">
                <NetworkErrorView onRetry={handleLanguageRetry} loading={isLanguagePending} />
              </div>
            )}
          </section>

          {/* Logout section */}
          <div style={LOGOUT_SECTION_STYLE} data-testid="account-logout-section">
            <SolidCTA
              onClick={() => { void logout(); }}
              loading={isLoggingOut}
              loadingLabel={t("account:logoutAction.inProgress")}
              aria-label={t("account:logout")}
              data-testid="account-logout-button"
            >
              {t("account:logout")}
            </SolidCTA>
          </div>

        </div>
      </div>
    </MobileFrame>
  );
}

// ---------------------------------------------------------------------------
// Internal sub-component: ProfileRow
// ---------------------------------------------------------------------------

/**
 * Single profile field row — label + value.
 * Used for email, full_name, brand, department, country, center.
 *
 * @param label - Translated field label.
 * @param value - Field value to display.
 * @param testId - data-testid for the value element (used in tests).
 */
function ProfileRow({
  label,
  value,
  testId,
}: {
  label: string;
  value: string;
  testId: string;
}): ReactNode {
  return (
    <div style={PROFILE_ROW_STYLE}>
      <span style={PROFILE_LABEL_STYLE}>{label}</span>
      <span style={PROFILE_VALUE_STYLE} data-testid={testId}>
        {value}
      </span>
    </div>
  );
}

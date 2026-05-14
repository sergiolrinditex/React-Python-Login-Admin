/**
 * Hilo People — AccountPage.
 *
 * Slice/Phase: P03-S02-T004 — AccountPage / Phase 3.
 *
 * Responsibility: Employee profile page — language selector + logout.
 *   Route: /account (RequireAuth — any authenticated user).
 *   Journey: J102 (language change leg).
 *
 * Implements 5 required UX states (empty: N/A for authenticated profile):
 *   loading          — initial profile fetch in progress (aria-busy skeleton)
 *   error_network    — UserNetworkError/UserServerError from useMe → retry CTA
 *   error_validation — 400/422 from updateLanguage → inline error near picker
 *   permission_denied — 403 from useMe → ForbiddenView block
 *   success          — profile + language picker (ES/EN/FR) + logout action
 *
 * Decisions applied (§D-T004-*):
 *   D-T004-LANGUAGE-OPTIMISTIC: language switches instantly, PATCH confirms server-side.
 *   D-T004-LOGOUT-REUSE: calls useAuth().logout() directly — no new repo method.
 *   D-T004-LOGOUT-CONFIRM: NO confirmation modal in V1 (single tap → logout).
 *   D-T004-NAV-BACK: NO custom back button — browser back sufficient for V1.
 *   D-T004-LANG-PICKER-VARIANT: 3-button radiogroup (not <select>).
 *   D-T004-LOGOUT-AS-UNDERLINED-ACTION: logout is underlined text action, not SolidCTA.
 *   D-T004-I18N-DETECTOR-OFF: detector stays OFF; i18n synced via changeLanguage() on render.
 *
 * Security: NEVER log email, full_name, tokens. Log user_id + language code only.
 * Non-negotiables §logging: BEFORE + AFTER + ERROR gated by VITE_ENABLE_VERBOSE_LOGGING.
 */

import { type ReactNode, useCallback, useEffect } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import MobileFrame from "../../shared/design-system/MobileFrame";
import TrackedLabel from "../../shared/design-system/TrackedLabel";
import { useAuth } from "../../features/auth/presentation/AuthProvider";
import { useMe } from "../../features/user/presentation/useMe";
import { useUpdateLanguage } from "../../features/user/presentation/useUpdateLanguage";
import { UserForbiddenError, UserNetworkError, UserServerError } from "../../features/user/domain/types";
import type { LanguageCode } from "../../features/user/domain/types";
import { logVerbose, logWarn, logError } from "../../features/user/data/logger";
import {
  PAGE_STYLE,
  SECTION_STYLE,
  PROFILE_ROW_STYLE,
  PROFILE_VALUE_STYLE,
  LANG_PICKER_STYLE,
  LANG_BTN_BASE,
  LANG_BTN_ACTIVE,
  LOGOUT_BTN_STYLE,
  ERROR_TEXT_STYLE,
  INLINE_ERROR_STYLE,
  LOADING_STYLE,
  SKELETON_LINE_STYLE,
} from "./AccountPage.styles";
import { ForbiddenView, NetworkErrorView } from "./_AccountPage.error-views";

// ---------------------------------------------------------------------------
// Language options config
// ---------------------------------------------------------------------------

const LANGUAGE_OPTIONS: Array<{ code: LanguageCode; nativeKey: string }> = [
  { code: "es", nativeKey: "es" },
  { code: "en", nativeKey: "en" },
  { code: "fr", nativeKey: "fr" },
];

// ---------------------------------------------------------------------------
// AccountPage
// ---------------------------------------------------------------------------

/**
 * Employee account page: profile read-only view, language selector, logout.
 * Route: /account (RequireAuth — any authenticated user).
 *
 * @returns The account page element.
 */
export default function AccountPage(): ReactNode {
  const { t, i18n } = useTranslation(["account", "common", "errors"]);
  const navigate = useNavigate();
  const { logout } = useAuth();

  logVerbose("account.page.render.start");

  // ---------------------------------------------------------------------------
  // Data
  // ---------------------------------------------------------------------------

  const {
    data: profile,
    isPending,
    isError,
    error: meError,
    refetch,
  } = useMe();

  const handleAuthFailure = useCallback((): void => {
    logWarn("account.page.auth_failure_triggered");
    void logout();
  }, [logout]);

  const {
    mutate: updateLanguage,
    isPending: isUpdatingLanguage,
    error: langError,
    reset: resetLangError,
  } = useUpdateLanguage(handleAuthFailure);

  // §D-T004-I18N-DETECTOR-OFF: sync i18n with profile's preferred_language on mount.
  // Detector is OFF; language is set explicitly from backend source of truth.
  useEffect(() => {
    if (profile?.preferred_language !== undefined) {
      const current = i18n.language;
      if (current !== profile.preferred_language) {
        logVerbose("account.page.i18n_sync", {
          from: current,
          to: profile.preferred_language,
        });
        void i18n.changeLanguage(profile.preferred_language);
      }
    }
  }, [profile?.preferred_language, i18n]);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleLanguageSelect = useCallback(
    (lang: LanguageCode): void => {
      if (lang === profile?.preferred_language) return;
      if (isUpdatingLanguage) return;
      logVerbose("account.page.language_select", { language: lang });
      resetLangError();
      updateLanguage(lang);
    },
    [profile?.preferred_language, isUpdatingLanguage, updateLanguage, resetLangError],
  );

  const handleLogout = useCallback((): void => {
    logVerbose("account.page.logout.start");
    void logout().then(() => {
      logVerbose("account.page.logout.ok");
      void navigate("/auth/sign-in", { replace: true });
    }).catch((err: unknown) => {
      logError("account.page.logout.error", {
        error: err instanceof Error ? err.message : "unknown",
      });
      // Still navigate even on error (defensive logout)
      void navigate("/auth/sign-in", { replace: true });
    });
  }, [logout, navigate]);

  const handleRetry = useCallback((): void => {
    logVerbose("account.page.retry");
    void refetch();
  }, [refetch]);

  const handleForbiddenSignIn = useCallback((): void => {
    logWarn("account.page.forbidden_sign_in");
    void logout().then(() => {
      void navigate("/auth/sign-in");
    });
  }, [logout, navigate]);

  // ---------------------------------------------------------------------------
  // State classification
  // ---------------------------------------------------------------------------

  const isForbidden = isError && meError instanceof UserForbiddenError;
  const isNetworkError =
    isError && (meError instanceof UserNetworkError || meError instanceof UserServerError);
  const isLangValidationError = langError !== null && langError.code === "USER_VALIDATION_ERROR";
  const currentLanguage = profile?.preferred_language ?? i18n.language as LanguageCode;

  // ---------------------------------------------------------------------------
  // Loading state
  // ---------------------------------------------------------------------------

  if (isPending) {
    return (
      <MobileFrame asMain fullHeight>
        <div
          style={LOADING_STYLE}
          aria-busy="true"
          aria-label={t("common:states.loading")}
          data-testid="account-loading"
        >
          <div style={{ ...SKELETON_LINE_STYLE, width: "60%" }} />
          <div style={{ ...SKELETON_LINE_STYLE, width: "80%" }} />
          <div style={{ ...SKELETON_LINE_STYLE, width: "70%" }} />
          <div style={{ ...SKELETON_LINE_STYLE, width: "50%" }} />
        </div>
      </MobileFrame>
    );
  }

  // ---------------------------------------------------------------------------
  // Permission denied state (403)
  // ---------------------------------------------------------------------------

  if (isForbidden) {
    return (
      <MobileFrame asMain fullHeight>
        <ForbiddenView
          message={t("errors:AUTH_FORBIDDEN")}
          onSignIn={handleForbiddenSignIn}
        />
      </MobileFrame>
    );
  }

  // ---------------------------------------------------------------------------
  // Network error state (5xx / fetch fail)
  // ---------------------------------------------------------------------------

  if (isNetworkError) {
    return (
      <MobileFrame asMain fullHeight>
        <NetworkErrorView
          message={t("account:errors.network")}
          onRetry={handleRetry}
          loading={isPending}
        />
      </MobileFrame>
    );
  }

  // ---------------------------------------------------------------------------
  // Success state (+ error_validation inline if language update failed)
  // empty state: N/A — there is always a UserProfile when authenticated.
  // ---------------------------------------------------------------------------

  return (
    <MobileFrame asMain fullHeight>
      <div style={PAGE_STYLE} data-testid="account-page">

        {/* Page title */}
        <TrackedLabel as="h1" variant="active" style={{ fontSize: "1rem" }}>
          {t("account:title")}
        </TrackedLabel>

        {/* Profile section */}
        <section style={SECTION_STYLE} aria-label={t("account:profile.heading")} data-testid="profile-section">
          <TrackedLabel as="h2">
            {t("account:profile.heading")}
          </TrackedLabel>

          {profile !== undefined && (
            <>
              <div style={PROFILE_ROW_STYLE} data-testid="profile-row-name">
                <TrackedLabel>{t("account:profile.name")}</TrackedLabel>
                <span style={PROFILE_VALUE_STYLE}>{profile.full_name}</span>
              </div>

              <div style={PROFILE_ROW_STYLE} data-testid="profile-row-email">
                <TrackedLabel>{t("account:profile.email")}</TrackedLabel>
                <span style={PROFILE_VALUE_STYLE}>{profile.email}</span>
              </div>

              {profile.employee_profile !== null && profile.employee_profile !== undefined && (
                <>
                  <div style={PROFILE_ROW_STYLE} data-testid="profile-row-employee-id">
                    <TrackedLabel>{t("account:profile.employeeId")}</TrackedLabel>
                    <span style={PROFILE_VALUE_STYLE}>{profile.employee_profile.employee_id}</span>
                  </div>
                  <div style={PROFILE_ROW_STYLE} data-testid="profile-row-brand">
                    <TrackedLabel>{t("account:profile.brand")}</TrackedLabel>
                    <span style={PROFILE_VALUE_STYLE}>{profile.employee_profile.brand}</span>
                  </div>
                  <div style={PROFILE_ROW_STYLE} data-testid="profile-row-society">
                    <TrackedLabel>{t("account:profile.society")}</TrackedLabel>
                    <span style={PROFILE_VALUE_STYLE}>{profile.employee_profile.society}</span>
                  </div>
                  <div style={PROFILE_ROW_STYLE} data-testid="profile-row-center">
                    <TrackedLabel>{t("account:profile.center")}</TrackedLabel>
                    <span style={PROFILE_VALUE_STYLE}>{profile.employee_profile.center}</span>
                  </div>
                  <div style={PROFILE_ROW_STYLE} data-testid="profile-row-country">
                    <TrackedLabel>{t("account:profile.country")}</TrackedLabel>
                    <span style={PROFILE_VALUE_STYLE}>{profile.employee_profile.country}</span>
                  </div>
                  <div style={PROFILE_ROW_STYLE} data-testid="profile-row-department">
                    <TrackedLabel>{t("account:profile.department")}</TrackedLabel>
                    <span style={PROFILE_VALUE_STYLE}>{profile.employee_profile.department}</span>
                  </div>
                </>
              )}
            </>
          )}
        </section>

        {/* Language selector section */}
        <section style={SECTION_STYLE} aria-label={t("account:language")} data-testid="language-section">
          <TrackedLabel as="h2">{t("account:language")}</TrackedLabel>
          <p style={{ ...ERROR_TEXT_STYLE, opacity: 0.6, fontSize: "0.75rem" }}>
            {t("account:languageHint")}
          </p>

          {/* 3-button radiogroup — §D-T004-LANG-PICKER-VARIANT */}
          <div
            role="radiogroup"
            aria-label={t("account:language")}
            style={LANG_PICKER_STYLE}
            data-testid="language-picker"
          >
            {LANGUAGE_OPTIONS.map(({ code, nativeKey }) => {
              const isActive = currentLanguage === code;
              return (
                <button
                  key={code}
                  role="radio"
                  aria-checked={isActive}
                  aria-label={t(`common:language.${nativeKey}`)}
                  style={isActive ? LANG_BTN_ACTIVE : LANG_BTN_BASE}
                  onClick={() => { handleLanguageSelect(code); }}
                  disabled={isUpdatingLanguage}
                  data-testid={`lang-btn-${code}`}
                  type="button"
                >
                  <span aria-hidden="true">{isActive ? "●" : "○"}</span>
                  <span>{t(`common:language.${nativeKey}`)}</span>
                </button>
              );
            })}
          </div>

          {/* error_validation: inline error near picker (§D-T004-ERROR-MAPPING) */}
          {isLangValidationError && (
            <p
              role="alert"
              style={INLINE_ERROR_STYLE}
              data-testid="lang-validation-error"
            >
              {t("account:errors.languageUpdateFailed")}
            </p>
          )}

          {/* Network error from language update */}
          {langError !== null && !isLangValidationError && (
            <p
              role="alert"
              style={INLINE_ERROR_STYLE}
              data-testid="lang-network-error"
            >
              {t("account:errors.network")}
            </p>
          )}
        </section>

        {/* Logout section — §D-T004-LOGOUT-AS-UNDERLINED-ACTION */}
        <section style={SECTION_STYLE} data-testid="logout-section">
          <button
            type="button"
            style={LOGOUT_BTN_STYLE}
            onClick={handleLogout}
            aria-label={t("account:logout")}
            data-testid="logout-button"
          >
            {t("account:logout")}
          </button>
        </section>
      </div>
    </MobileFrame>
  );
}

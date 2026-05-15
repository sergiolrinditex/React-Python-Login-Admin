/**
 * Hilo People — TwoFactorPage component.
 *
 * Slice/Phase: P03-S01-T005 — TwoFactorPage (/auth/2fa editorial móvil) / Phase 3.
 *
 * Responsibility: Editorial mobile 2FA verification form (layout + local state + lifecycle).
 *   Business rules delegated to useVerifyMfa hook.
 *   One <input> for the 6-digit code (§D-T005-PASTE-HANDLING).
 *   Submit is MANUAL only — no auto-submit at 6 chars (§D-T005-AUTOSUBMIT-DISABLED).
 *
 * Required UI states (5):
 *   loading           — aria-busy="true" on CTA + input disabled during in-flight request.
 *   error_validation  — client-side length check OR server 400/401 form-level alert.
 *   error_network     — fetch TypeError or 5xx mapped to error_network bucket.
 *   permission_denied — 410 challenge expired (auto-redirect 1.5s) OR 429 rate limited.
 *   success           — 200 received + fetchMe done + navigate to /chat (or ?next=).
 *   empty = N/A       — form, per instrucciones §3.2 and T001/T002/T003 precedent.
 *
 * §D-T005-DEEP-LINK-GUARD: If no mfa_challenge_token in router state → redirect to /auth/sign-in.
 * §D-T005-AGGREGATE-401: ONE copy for all 401 variants (anti-enumeration; backend aggregates).
 * §D-T005-EXPIRED-CHALLENGE: 410 → 1.5s flash → auto-navigate /auth/sign-in.
 * §D-T005-NEXT-FORWARD: reads ?next= from search params, passes through getSafeRedirect.
 *
 * Route: /auth/2fa (public, no RequireAuth — §6.4 Navigation Contract).
 * Journey ref: J100 (participates — MFA step; does NOT close J100).
 *
 * Design: MobileFrame + Wordmark + TrackedLabel + EditorialInput + SolidCTA.
 *   All tokens from tokens.css. NO hardcoded colors/fonts/radii.
 *
 * Non-negotiables §logging, §a11y, §security enforced throughout.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
// Note: useMemo is used for `repo` memoization below
import { useNavigate, useLocation, useSearchParams } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslation } from "react-i18next";

import { useTwoFactorSchema, getErrorInfo } from "./twoFactorHelpers";
import type { TwoFactorFormValues } from "./twoFactorHelpers";

import MobileFrame from "@/shared/design-system/MobileFrame";
import Wordmark from "@/shared/design-system/Wordmark";
import TrackedLabel from "@/shared/design-system/TrackedLabel";
import EditorialInput from "@/shared/design-system/EditorialInput";
import SolidCTA from "@/shared/design-system/SolidCTA";

import { useAuth } from "@/features/auth/presentation/AuthProvider";
import { AuthRepository } from "@/features/auth/data/authRepository";
import { useVerifyMfa } from "@/features/auth/presentation/useVerifyMfa";
import { getSafeRedirect } from "@/features/auth/presentation/redirectAfterAuth";
import {
  MfaChallengeExpiredError,
  MfaVerifyRateLimitedError,
} from "@/features/auth/data/errors";
import { logVerbose, logWarn } from "@/features/auth/data/logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Delay in ms before auto-redirecting after a 410 challenge expired error. */
const EXPIRED_REDIRECT_DELAY_MS = 1500;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Editorial two-factor verification page — 6-digit code form with full UI state coverage.
 *
 * Reads mfa_challenge_token from react-router location.state (set by SignInPage on MFA branch).
 * §D-T005-DEEP-LINK-GUARD: redirects to /auth/sign-in if no token in state.
 *
 * @returns ReactElement
 */
export default function TwoFactorPage(): React.ReactElement {
  const { t } = useTranslation("auth");
  const { signInAccepted } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  // §D-T005-NEXT-FORWARD: read ?next= from search params
  const rawNext = searchParams.get("next");
  const safeNext = getSafeRedirect(rawNext);

  // Read mfa_challenge_token from router state (set by SignInPage on MFA branch)
  const routerState = location.state as { mfa_challenge_token?: string; expires_in?: number } | null;
  const challengeToken = routerState?.mfa_challenge_token ?? "";

  // §D-T005-DEEP-LINK-GUARD: if no valid challenge token, bounce to sign-in
  const redirectedRef = useRef(false);
  useEffect(() => {
    if (!challengeToken && !redirectedRef.current) {
      redirectedRef.current = true;
      logWarn("auth.twofactor.page.missing_challenge");
      void navigate("/auth/sign-in", { replace: true });
    }
  }, [challengeToken, navigate]);

  const schema = useTwoFactorSchema();

  const {
    register,
    handleSubmit,
    formState: { errors },
    setValue,
  } = useForm<TwoFactorFormValues>({
    resolver: zodResolver(schema),
    mode: "onTouched",
  });

  const repo = useMemo(() => new AuthRepository(() => void 0), []);
  const { submit, isLoading, error: verifyError, clearError } = useVerifyMfa(repo, signInAccepted);

  // §D-T005-EXPIRED-CHALLENGE: auto-redirect to /auth/sign-in after 1.5s on 410
  const [isExpiredRedirecting, setIsExpiredRedirecting] = useState(false);
  useEffect(() => {
    if (verifyError instanceof MfaChallengeExpiredError && !isExpiredRedirecting) {
      setIsExpiredRedirecting(true);
      const timer = setTimeout(() => {
        void navigate("/auth/sign-in", { replace: true });
      }, EXPIRED_REDIRECT_DELAY_MS);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [verifyError, isExpiredRedirecting, navigate]);

  // ---------------------------------------------------------------------------
  // Form submit handler
  // ---------------------------------------------------------------------------

  const onSubmit = useCallback(
    async (values: TwoFactorFormValues) => {
      logVerbose("auth.twofactor.page.submit.start", {
        challenge_token_len: challengeToken.length,
        code_len: values.code.length,
      });

      clearError();
      const outcome = await submit({ challengeToken, code: values.code });

      if (!outcome) {
        logWarn("auth.twofactor.page.submit.failed");
        return;
      }

      // Success — signInAccepted already called by useVerifyMfa
      logVerbose("auth.twofactor.page.submit.success_navigate", { destination: safeNext });
      navigate(safeNext, { replace: true });
    },
    [submit, clearError, navigate, safeNext, challengeToken],
  );

  // ---------------------------------------------------------------------------
  // Error mapping for UI display
  // ---------------------------------------------------------------------------

  const serverErrorInfo = verifyError ? getErrorInfo(verifyError) : null;
  const serverErrorText = serverErrorInfo
    ? t(serverErrorInfo.key, serverErrorInfo.interpolation as Record<string, string>)
    : null;

  const isRateLimited = verifyError instanceof MfaVerifyRateLimitedError;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  logVerbose("auth.twofactor.page.render.start", { isLoading, hasError: Boolean(verifyError) });

  // While redirecting due to missing challenge or expired challenge, show nothing
  if (!challengeToken) {
    return <></>;
  }

  return (
    <MobileFrame asMain>
      {/* Brand header */}
      <div style={{ marginBottom: "2rem" }}>
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "2rem",
            color: "var(--color-ink)",
            margin: 0,
            lineHeight: 1.1,
          }}
        >
          <Wordmark size="2rem" aria-label="Hilo" />
        </h1>
      </div>

      {/* Section label */}
      <TrackedLabel
        as="p"
        variant="default"
        style={{ marginBottom: "0.5rem", display: "block" }}
      >
        {t("twoFactor.titleHint")}
      </TrackedLabel>

      {/* Page title */}
      <p
        style={{
          fontFamily: "var(--font-display)",
          fontSize: "1.375rem",
          color: "var(--color-ink)",
          margin: "0 0 1rem 0",
          lineHeight: 1.25,
        }}
      >
        {t("twoFactor.title")}
      </p>

      {/* Intro text */}
      <p
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: "0.875rem",
          color: "var(--color-ink)",
          margin: "0 0 2rem 0",
          opacity: 0.75,
        }}
      >
        {t("twoFactor.intro")}
      </p>

      {/* Form-level error region (error_validation, permission_denied, error_network) */}
      {serverErrorText && (
        <div
          role="alert"
          aria-live="assertive"
          data-testid="twofactor-form-error"
          data-error-state={serverErrorInfo?.state}
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.875rem",
            color: "var(--color-ink)",
            borderBottom: "2px solid var(--color-ink)",
            padding: "0.75rem 0",
            marginBottom: "1.25rem",
            opacity: 0.9,
          }}
        >
          {serverErrorText}
          {/* §D-T005-EXPIRED-CHALLENGE: CTA to go back on expired challenge */}
          {verifyError instanceof MfaChallengeExpiredError && (
            <span
              style={{
                display: "block",
                marginTop: "0.5rem",
                fontFamily: "var(--font-sans)",
                fontSize: "0.875rem",
                color: "var(--color-ink)",
                cursor: "pointer",
                textDecoration: "underline",
              }}
              role="button"
              tabIndex={0}
              data-testid="twofactor-back-to-signin"
              onClick={() => { void navigate("/auth/sign-in", { replace: true }); }}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") void navigate("/auth/sign-in", { replace: true }); }}
              aria-label={t("twoFactor.actions.backToSignIn")}
            >
              {t("twoFactor.actions.backToSignIn")}
            </span>
          )}
        </div>
      )}

      {/* 2FA form */}
      <form
        onSubmit={handleSubmit(onSubmit)}
        noValidate
        aria-label={t("twoFactor.title")}
        style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}
      >
        <EditorialInput
          label={t("twoFactor.codeLabel")}
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder={t("twoFactor.codePlaceholder")}
          disabled={isLoading || isRateLimited || isExpiredRedirecting}
          maxLength={6}
          aria-label={t("twoFactor.codeLabel")}
          aria-invalid={Boolean(errors.code) || Boolean(verifyError && serverErrorInfo?.state === "error_validation")}
          {...register("code", {
            onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
              // §D-T005-PASTE-HANDLING: strip whitespace, keep only digits
              const cleaned = e.target.value.replace(/\D/g, "").slice(0, 6);
              setValue("code", cleaned, { shouldValidate: true });
            },
          })}
        />

        {/* Field-level validation error */}
        {errors.code && (
          <p
            role="alert"
            aria-live="assertive"
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "0.8125rem",
              color: "var(--color-ink)",
              margin: "-0.75rem 0 0 0",
              opacity: 0.85,
            }}
            data-testid="twofactor-code-error"
          >
            {errors.code.message}
          </p>
        )}

        <SolidCTA
          type="submit"
          disabled={isLoading || isRateLimited || isExpiredRedirecting}
          loading={isLoading}
          loadingLabel={t("twoFactor.status.submitting")}
          aria-busy={isLoading}
        >
          {t("twoFactor.cta")}
        </SolidCTA>
      </form>
    </MobileFrame>
  );
}

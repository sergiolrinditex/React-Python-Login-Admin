/**
 * Hilo People — SignInPage component.
 *
 * Slice/Phase: P03-S01-T001 — SignInPage (Login email/password editorial móvil) / Phase 3.
 *
 * Responsibility: Editorial mobile sign-in form.
 *   Handles email + password validation via react-hook-form + zod.
 *   All 5 required UI states: loading, error_validation, error_network,
 *   permission_denied, success.
 *   i18n via react-i18next (namespace "auth", keys under signIn.*).
 *   Navigates to /auth/2fa (MFA) or ?next= / /chat (success).
 *
 * Route: /auth/sign-in (public, no auth required).
 * Journey ref: J100 (first screen — credential step).
 *
 * Design: MobileFrame + Wordmark + TrackedLabel + EditorialInput + SolidCTA.
 *   All tokens from tokens.css. NO hardcoded colors/fonts/radii.
 *   No rounded cards, no box shadows, hairline borders only.
 *
 * Decision log (§9 task pack):
 *   D-T001-CHALLENGE-TRANSPORT: mfa_challenge_token via navigate(...,{state}) (react-router v7).
 *   D-T001-NEXT-FORWARD: ?next= forwarded to /auth/2fa?next=<safe> on MFA branch.
 *   D-T001-PASSWORD-MIN: zod min(1) on sign-in (no creation policy).
 *   D-T001-EMAIL-CORP: zod .email() only — no corporate domain regex this slice.
 *
 * Non-negotiables §logging, §a11y, §security enforced throughout.
 */

import { useCallback, useMemo } from "react";
import { useNavigate, useSearchParams, Link } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";

import MobileFrame from "@/shared/design-system/MobileFrame";
import Wordmark from "@/shared/design-system/Wordmark";
import TrackedLabel from "@/shared/design-system/TrackedLabel";
import EditorialInput from "@/shared/design-system/EditorialInput";
import SolidCTA from "@/shared/design-system/SolidCTA";

import { useAuth } from "@/features/auth/presentation/AuthProvider";
import { AuthRepository } from "@/features/auth/data/authRepository";
import { useSignIn } from "@/features/auth/presentation/useSignIn";
import { getSafeRedirect } from "@/features/auth/presentation/redirectAfterAuth";
import {
  InvalidCredentialsError,
  AccountLockedError,
  RateLimitedError,
  NetworkError,
} from "@/features/auth/data/errors";
import { logVerbose, logWarn } from "@/features/auth/data/logger";

// ---------------------------------------------------------------------------
// Route constants
// ---------------------------------------------------------------------------

export const ROUTE_AUTH_2FA = "/auth/2fa";

// ---------------------------------------------------------------------------
// Zod schema — D-T001-PASSWORD-MIN: min(1) on sign-in only (no creation policy)
// ---------------------------------------------------------------------------

function useSignInSchema() {
  const { t } = useTranslation("auth");
  return useMemo(
    () =>
      z.object({
        email: z
          .string()
          .min(1, t("signIn.errors.emailRequired"))
          .email(t("signIn.errors.emailFormat")),
        password: z.string().min(1, t("signIn.errors.passwordRequired")),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
}

type SignInFormValues = { email: string; password: string };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Maps a sign-in error to the correct UI state and i18n key. */
function getErrorI18nKey(
  err: Error,
  retryAfterSeconds?: number,
): { key: string; interpolation?: Record<string, string | number>; state: "error_validation" | "permission_denied" | "error_network" } {
  if (err instanceof InvalidCredentialsError) {
    return { key: "signIn.errors.invalidCredentials", state: "error_validation" };
  }
  if (err instanceof AccountLockedError) {
    return { key: "signIn.errors.accountLocked", state: "permission_denied" };
  }
  if (err instanceof RateLimitedError) {
    return {
      key: "signIn.errors.rateLimited",
      interpolation: { seconds: retryAfterSeconds ?? err.retryAfter },
      state: "permission_denied",
    };
  }
  if (err instanceof NetworkError) {
    return { key: "signIn.errors.network", state: "error_network" };
  }
  return { key: "signIn.errors.serverInternal", state: "error_network" };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Editorial sign-in page — email/password form with full UI state coverage.
 *
 * @returns ReactElement
 */
export default function SignInPage(): React.ReactElement {
  const { t } = useTranslation("auth");
  const { signInAccepted } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const schema = useSignInSchema();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignInFormValues>({
    resolver: zodResolver(schema),
    mode: "onTouched",
  });

  // ---------------------------------------------------------------------------
  // Build repo (non-injectable in prod; injectable in tests via wrapper)
  // ---------------------------------------------------------------------------

  const repo = useMemo(() => new AuthRepository(() => void 0), []);
  const { submit, isLoading, error: signInError, clearError } = useSignIn(repo, signInAccepted);

  // ---------------------------------------------------------------------------
  // Navigation helpers
  // ---------------------------------------------------------------------------

  const rawNext = searchParams.get("next");
  const safeNext = getSafeRedirect(rawNext);

  // ---------------------------------------------------------------------------
  // Form submit handler
  // ---------------------------------------------------------------------------

  const onSubmit = useCallback(
    async (values: SignInFormValues) => {
      logVerbose("auth.signin.page.submit.start", {
        email_domain: values.email.includes("@") ? values.email.split("@")[1] : "unknown",
      });
      clearError();
      const outcome = await submit({ email: values.email, password: values.password });

      if (!outcome) {
        logWarn("auth.signin.page.submit.failed");
        return;
      }

      if (outcome.kind === "mfa") {
        // D-T001-CHALLENGE-TRANSPORT: router state (no URL exposure of token)
        // D-T001-NEXT-FORWARD: forward ?next= so TwoFactorPage preserves deep link
        const target = safeNext !== "/chat"
          ? `${ROUTE_AUTH_2FA}?next=${encodeURIComponent(safeNext)}`
          : ROUTE_AUTH_2FA;
        logVerbose("auth.signin.page.submit.mfa_navigate", { target });
        navigate(target, {
          state: {
            mfa_challenge_token: outcome.challengeToken,
            expires_in: outcome.expiresIn,
          },
        });
        return;
      }

      // No-MFA success — signInAccepted already called by useSignIn
      logVerbose("auth.signin.page.submit.success_navigate", { destination: safeNext });
      navigate(safeNext, { replace: true });
    },
    [submit, clearError, navigate, safeNext],
  );

  // ---------------------------------------------------------------------------
  // Error mapping for UI display
  // ---------------------------------------------------------------------------

  const serverErrorInfo = signInError
    ? getErrorI18nKey(signInError, signInError instanceof RateLimitedError ? signInError.retryAfter : undefined)
    : null;

  const serverErrorText = serverErrorInfo
    ? t(serverErrorInfo.key, serverErrorInfo.interpolation as Record<string, string>)
    : null;

  // Disable submit on rate-limit (D-T001-FOCUS-MGMT: simple disabled flag, KISS)
  const isRateLimited = signInError instanceof RateLimitedError;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  logVerbose("auth.signin.page.render.start", { isLoading, hasError: Boolean(signInError) });

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
        {t("signIn.titleHint")}
      </TrackedLabel>

      {/* Page title */}
      <p
        style={{
          fontFamily: "var(--font-display)",
          fontSize: "1.375rem",
          color: "var(--color-ink)",
          margin: "0 0 2rem 0",
          lineHeight: 1.25,
        }}
      >
        {t("signIn.title")}
      </p>

      {/* Form-level error region (error_network, error_validation, permission_denied) */}
      {serverErrorText && (
        <div
          role="alert"
          aria-live="polite"
          data-testid="signin-form-error"
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
        </div>
      )}

      {/* Sign-in form */}
      <form
        onSubmit={handleSubmit(onSubmit)}
        noValidate
        aria-label={t("signIn.title")}
        style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}
      >
        <EditorialInput
          label={t("signIn.email")}
          type="email"
          autoComplete="username"
          placeholder={t("signIn.emailPlaceholder")}
          disabled={isLoading}
          errorMessage={errors.email?.message}
          data-testid="signin-email-input"
          {...register("email")}
        />

        <EditorialInput
          label={t("signIn.password")}
          type="password"
          autoComplete="current-password"
          placeholder={t("signIn.passwordPlaceholder")}
          disabled={isLoading}
          errorMessage={errors.password?.message}
          data-testid="signin-password-input"
          {...register("password")}
        />

        <div style={{ marginTop: "0.5rem" }}>
          <SolidCTA
            type="submit"
            loading={isLoading}
            disabled={isRateLimited}
            loadingLabel={t("signIn.status.submitting")}
            data-testid="signin-submit-button"
          >
            {t("signIn.submit")}
          </SolidCTA>
        </div>
      </form>

      {/* Secondary navigation links */}
      <nav
        style={{
          marginTop: "1.75rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.75rem",
        }}
        aria-label="Auth navigation"
      >
        <Link
          to="/auth/sign-up"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.875rem",
            color: "var(--color-ink)",
            textDecoration: "underline",
          }}
          data-testid="signin-link-signup"
        >
          {t("signIn.actions.signUp")}
        </Link>

        <Link
          to="/auth/forgot-password"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.875rem",
            color: "var(--color-ink)",
            textDecoration: "underline",
          }}
          data-testid="signin-link-forgot"
        >
          {t("signIn.actions.forgot")}
        </Link>
      </nav>
    </MobileFrame>
  );
}

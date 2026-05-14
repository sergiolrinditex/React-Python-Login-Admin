/**
 * Hilo People — SignUpPage component.
 *
 * Slice/Phase: P03-S01-T002 — SignUpPage (registro email/password editorial móvil) / Phase 3.
 *
 * Responsibility: Editorial mobile sign-up form (layout + local state + lifecycle only).
 *   Business rules delegated to useSignUp hook; schema + error mapping in signUpHelpers.ts.
 *   All 5 required UI states: loading, error_validation, error_network,
 *   permission_denied, success. (empty: N/A for forms per instrucciones §3.2.)
 *   i18n via react-i18next (namespace "auth", keys under signUp.*).
 *   On success (201): navigates to /auth/sign-in with flash state (D-T002-SUCCESS-REDIRECT).
 *
 * Route: /auth/sign-up (public, no auth required).
 * Journey ref: J100 (participates — credential creation step).
 *
 * Design: MobileFrame + Wordmark + TrackedLabel + EditorialInput + SolidCTA
 *   + inline editorial checkbox (D-T002-CHECKBOX-INLINE).
 *   All tokens from tokens.css. NO hardcoded colors/fonts/radii.
 *   No rounded cards, no box shadows, hairline borders only.
 *
 * Decision log (§15 task pack):
 *   D-T002-PROACTIVE-EXTRACT: schema + error mapper extracted to signUpHelpers.ts
 *     to keep this file ≤300 LoC self-contained (applied at 367 eff. lines).
 *   D-T002-SUCCESS-REDIRECT: navigate to /auth/sign-in with flash state after 201.
 *   D-T002-NO-NEXT-PARAM: sign-up passes ?next= through to /auth/sign-in if present.
 *   D-T002-CHECKBOX-INLINE: inline editorial checkbox — no new base component.
 *   D-T002-409-NO-FIELD: 409 EMAIL_TAKEN → generic copy, no email field highlight.
 *   D-T002-PII-LOGGING: email_domain only in logs; never full email, password, full_name.
 *
 * Non-negotiables §logging, §a11y, §security enforced throughout.
 */

import { useCallback, useMemo } from "react";
import { useNavigate, useSearchParams, Link } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslation } from "react-i18next";

import MobileFrame from "@/shared/design-system/MobileFrame";
import Wordmark from "@/shared/design-system/Wordmark";
import TrackedLabel from "@/shared/design-system/TrackedLabel";
import EditorialInput from "@/shared/design-system/EditorialInput";
import SolidCTA from "@/shared/design-system/SolidCTA";

import { AuthRepository } from "@/features/auth/data/authRepository";
import { useSignUp } from "@/features/auth/presentation/useSignUp";
import { SignupRateLimitedError } from "@/features/auth/data/errors";
import { logVerbose, logWarn } from "@/features/auth/data/logger";

import { useSignUpSchema, getSignUpErrorI18nKey } from "./signUpHelpers";
import type { SignUpFormValues } from "./signUpHelpers";

// ---------------------------------------------------------------------------
// Route constant (used for post-success redirect)
// ---------------------------------------------------------------------------

const ROUTE_AUTH_SIGN_IN = "/auth/sign-in";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Editorial sign-up page — corporate email / full_name / password / legal form.
 *
 * Thin layout + state-binding component; orchestration delegated to useSignUp hook.
 *
 * @returns ReactElement
 */
export default function SignUpPage(): React.ReactElement {
  const { t } = useTranslation("auth");
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const schema = useSignUpSchema();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignUpFormValues>({
    resolver: zodResolver(schema),
    mode: "onTouched",
    defaultValues: {
      email: "",
      full_name: "",
      password: "",
      legal_acceptance: false,
    },
  });

  // ---------------------------------------------------------------------------
  // Repository (non-injectable in prod; injectable in tests via wrapper)
  // ---------------------------------------------------------------------------

  const repo = useMemo(() => new AuthRepository(() => void 0), []);

  const onSuccess = useCallback(
    (outcome: { user_id: string; mfa_required: false }) => {
      // D-T002-SUCCESS-REDIRECT: navigate to /auth/sign-in with flash state.
      // D-T002-NO-NEXT-PARAM: preserve any ?next= so sign-in can forward it.
      logVerbose("auth.signup.page.submit.success_navigate", {
        user_id: outcome.user_id,
      });
      const rawNext = searchParams.get("next");
      const destination = rawNext
        ? `${ROUTE_AUTH_SIGN_IN}?next=${encodeURIComponent(rawNext)}`
        : ROUTE_AUTH_SIGN_IN;
      navigate(destination, {
        replace: true,
        state: { flash: "account_created" },
      });
    },
    [navigate, searchParams],
  );

  const { submit, isLoading, error: signUpError, clearError } = useSignUp(repo, onSuccess);

  // ---------------------------------------------------------------------------
  // Form submit handler
  // ---------------------------------------------------------------------------

  const onSubmit = useCallback(
    async (values: SignUpFormValues) => {
      logVerbose("auth.signup.page.submit.start", {
        email_domain: values.email.includes("@") ? values.email.split("@")[1] : "unknown",
      });
      clearError();

      const outcome = await submit({
        email: values.email,
        password: values.password,
        full_name: values.full_name,
        legal_acceptance: true,
      });

      if (!outcome) {
        logWarn("auth.signup.page.submit.failed");
      }
    },
    [submit, clearError],
  );

  // ---------------------------------------------------------------------------
  // Error mapping for UI display
  // ---------------------------------------------------------------------------

  const serverErrorInfo = signUpError ? getSignUpErrorI18nKey(signUpError) : null;
  const serverErrorText = serverErrorInfo
    ? t(serverErrorInfo.key, serverErrorInfo.interpolation as Record<string, string>)
    : null;

  const isRateLimited = signUpError instanceof SignupRateLimitedError;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  logVerbose("auth.signup.page.render.start", { isLoading, hasError: Boolean(signUpError) });

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
        {t("signUp.titleHint")}
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
        {t("signUp.title")}
      </p>

      {/* Form-level error region (error_network, error_validation, permission_denied) */}
      {serverErrorText && (
        <div
          role="alert"
          aria-live="polite"
          data-testid="signup-form-error"
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

      {/* Sign-up form */}
      <form
        onSubmit={handleSubmit(onSubmit)}
        noValidate
        aria-label={t("signUp.title")}
        style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}
      >
        <EditorialInput
          label={t("signUp.email")}
          type="email"
          autoComplete="username"
          placeholder={t("signUp.emailPlaceholder")}
          disabled={isLoading}
          errorMessage={errors.email?.message}
          data-testid="signup-email-input"
          {...register("email")}
        />

        <EditorialInput
          label={t("signUp.fullName")}
          type="text"
          autoComplete="name"
          placeholder={t("signUp.fullNamePlaceholder")}
          disabled={isLoading}
          errorMessage={errors.full_name?.message}
          data-testid="signup-fullname-input"
          {...register("full_name")}
        />

        <EditorialInput
          label={t("signUp.password")}
          type="password"
          autoComplete="new-password"
          placeholder={t("signUp.passwordPlaceholder")}
          disabled={isLoading}
          errorMessage={errors.password?.message}
          data-testid="signup-password-input"
          {...register("password")}
        />

        {/* Password hint */}
        <p
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.75rem",
            color: "var(--color-ink)",
            margin: "-0.75rem 0 0 0",
            opacity: 0.65,
          }}
        >
          {t("signUp.passwordHint")}
        </p>

        {/* Legal acceptance checkbox — D-T002-CHECKBOX-INLINE: inline editorial style */}
        <div
          style={{ display: "flex", flexDirection: "column", gap: "0.375rem" }}
          data-testid="signup-legal-wrapper"
        >
          <label
            htmlFor="signup-legal-checkbox"
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "0.625rem",
              cursor: isLoading ? "not-allowed" : "pointer",
              fontFamily: "var(--font-sans)",
              fontSize: "0.875rem",
              color: "var(--color-ink)",
              lineHeight: 1.4,
            }}
          >
            {/* Editorial checkbox: hairline border, no radius (tokens: --hairline, --radius:0) */}
            <input
              id="signup-legal-checkbox"
              type="checkbox"
              disabled={isLoading}
              aria-describedby={
                errors.legal_acceptance ? "signup-legal-error" : "signup-legal-hint"
              }
              aria-invalid={errors.legal_acceptance ? "true" : undefined}
              data-testid="signup-legal-checkbox"
              style={{
                flexShrink: 0,
                width: "1.125rem",
                height: "1.125rem",
                marginTop: "0.1rem",
                borderRadius: "var(--radius, 0)",
                border: "var(--hairline) solid var(--color-ink)",
                accentColor: "var(--color-ink)",
                cursor: isLoading ? "not-allowed" : "pointer",
              }}
              {...register("legal_acceptance")}
            />
            <span>{t("signUp.legalAcceptance")}</span>
          </label>

          {/* Field-level error for legal_acceptance */}
          {errors.legal_acceptance && (
            <p
              id="signup-legal-error"
              role="alert"
              style={{
                fontFamily: "var(--font-sans)",
                fontSize: "0.75rem",
                color: "var(--color-ink)",
                margin: 0,
                opacity: 0.9,
              }}
              data-testid="signup-legal-error"
            >
              {errors.legal_acceptance.message}
            </p>
          )}

          {!errors.legal_acceptance && (
            <p
              id="signup-legal-hint"
              style={{
                fontFamily: "var(--font-sans)",
                fontSize: "0.75rem",
                color: "var(--color-ink)",
                margin: 0,
                opacity: 0.55,
              }}
            >
              {t("signUp.legalAcceptanceHint")}
            </p>
          )}
        </div>

        <div style={{ marginTop: "0.5rem" }}>
          <SolidCTA
            type="submit"
            loading={isLoading}
            disabled={isRateLimited}
            loadingLabel={t("signUp.status.submitting")}
            data-testid="signup-submit-button"
          >
            {t("signUp.submit")}
          </SolidCTA>
        </div>
      </form>

      {/* Secondary navigation link */}
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
          to={ROUTE_AUTH_SIGN_IN}
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.875rem",
            color: "var(--color-ink)",
            textDecoration: "underline",
          }}
          data-testid="signup-link-signin"
        >
          {t("signUp.actions.signIn")}
        </Link>
      </nav>
    </MobileFrame>
  );
}

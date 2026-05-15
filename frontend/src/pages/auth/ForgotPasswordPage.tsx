/**
 * Hilo People — ForgotPasswordPage component.
 *
 * Slice/Phase: P03-S01-T003 — ForgotPasswordPage (recuperación de acceso editorial móvil) / Phase 3.
 *
 * Responsibility: Editorial mobile forgot-password form (layout + local state + lifecycle only).
 *   Business rules delegated to useForgotPassword hook; schema + error mapping inline
 *   (1-field form is small enough — no helpers extract needed, §D-T003-FILESIZE-PROACTIVE).
 *
 * Required UI states (4):
 *   loading        — aria-busy="true" on CTA + disabled during in-flight request.
 *   error_validation — zod inline field error OR server 400/429 form-level alert.
 *   error_network  — fetch TypeError or 5xx mapped to error_network bucket.
 *   success        — opaque success flash card; navigates to /auth/reset-sent (D-T003-SUCCESS-REDIRECT).
 *
 * Anti-enumeration (§D-T003-ANTI-ENUM-UI):
 *   permission_denied = N/A — anti-enumeration design (server returns 200 for ALL valid
 *   email syntax inputs; never reveals whether email is registered or not).
 *   empty = N/A — form, per instrucciones §3.2 and T001/T002 precedent.
 *
 * VISUAL_CONTRACT_CHECK.required_states_covered:
 *   loading, error_validation, error_network, success,
 *   permission_denied=N/A — anti-enumeration design (server returns 200 for all valid email syntax; never reveals existence),
 *   empty=N/A — form, per instrucciones §3.2 and T001/T002 precedent.
 *
 * Route: /auth/forgot-password (public, no auth required, §D-T003-ROUTER).
 * Journey ref: J100 (participates — recoverability lateral; does NOT close J100).
 *
 * Design: MobileFrame + Wordmark + TrackedLabel + EditorialInput + SolidCTA.
 *   All tokens from tokens.css. NO hardcoded colors/fonts/radii.
 *   No rounded cards, no box shadows, hairline borders only. Same kit as T001/T002.
 *
 * Decision log (§15 task pack):
 *   D-T003-SUCCESS-REDIRECT: navigate to /auth/reset-sent with {state:{email}} after 200.
 *     T004 ResetSentPage doesn't exist yet — catch-all redirects to / → sign-in. Acceptable.
 *   D-T003-MASK-EMAIL: pass the user-typed email to /auth/reset-sent state so T004 can render
 *     it; but do NOT echo "email was found in DB" — always show same opaque success copy.
 *   D-T003-NO-NEXT-PARAM: forgot does NOT consume ?next= (not session-creating).
 *   D-T003-PII-LOGGING: email_domain + email_local_len only in logs; NEVER full email.
 *   D-T003-ANTI-ENUM-UI: unknown email returns same success as known email — UI identical.
 *   D-T003-FILESIZE-PROACTIVE: helpers extract not needed (1-field form ~200 eff. lines).
 *   D-T003-AUTH-DATA: ADR-002 same-origin — API_BASE="" relative URL (mirrored in hook→repo).
 *
 * Non-negotiables §logging, §a11y, §security enforced throughout.
 */

import { useCallback, useMemo, useState } from "react";
import { useNavigate, Link } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";

import MobileFrame from "@/shared/design-system/MobileFrame";
import Wordmark from "@/shared/design-system/Wordmark";
import TrackedLabel from "@/shared/design-system/TrackedLabel";
import EditorialInput from "@/shared/design-system/EditorialInput";
import SolidCTA from "@/shared/design-system/SolidCTA";

import { AuthRepository } from "@/features/auth/data/authRepository";
import { useForgotPassword } from "@/features/auth/presentation/useForgotPassword";
import { ForgotPasswordRateLimitedError } from "@/features/auth/data/errors";
import { logVerbose, logWarn } from "@/features/auth/data/logger";
import type { ForgotPasswordOutcome } from "@/features/auth/domain/AuthRepository";

// ---------------------------------------------------------------------------
// Route constants (D-T003-ROUTER, D-T003-SUCCESS-REDIRECT)
// ---------------------------------------------------------------------------

const ROUTE_AUTH_SIGN_IN = "/auth/sign-in";
const ROUTE_AUTH_RESET_SENT = "/auth/reset-sent"; // T004 destination (may not exist yet)

// ---------------------------------------------------------------------------
// Form schema
// ---------------------------------------------------------------------------

/** Zod schema for the forgot-password form (1 field — email only). */
function useForgotPasswordSchema() {
  const { t } = useTranslation("auth");
  return useMemo(
    () =>
      z.object({
        email: z
          .string()
          .min(1, t("forgot.errors.emailRequired"))
          .email(t("forgot.errors.emailFormat")),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
}

type ForgotPasswordFormValues = { email: string };

// ---------------------------------------------------------------------------
// Error mapper
// ---------------------------------------------------------------------------

type ForgotErrorInfo = {
  key: string;
  interpolation?: Record<string, string | number>;
  state: "error_validation" | "error_network";
};

/**
 * Maps a typed domain error from useForgotPassword to the correct i18n key and UI state.
 * Anti-enumeration: no permission_denied state — all 200 paths (known/unknown email) show success.
 */
function getForgotErrorI18nKey(err: Error): ForgotErrorInfo {
  if (err instanceof ForgotPasswordRateLimitedError) {
    return {
      key: "forgot.errors.rateLimited",
      interpolation: { seconds: err.retryAfter },
      state: "error_validation",
    };
  }
  // ForgotPasswordValidationError (400 — syntax; rare — zod catches first)
  if ("code" in err && (err as { code: string }).code === "AUTH_FORGOT_VALIDATION") {
    return { key: "forgot.errors.validation", state: "error_validation" };
  }
  // NetworkError or ForgotPasswordInternalError → error_network bucket
  if ("code" in err && (err as { code: string }).code === "NETWORK_ERROR") {
    return { key: "forgot.errors.network", state: "error_network" };
  }
  return { key: "forgot.errors.serverInternal", state: "error_network" };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Editorial forgot-password page — single email field form.
 *
 * Thin layout + state-binding component; orchestration delegated to useForgotPassword hook.
 * Handles 4 required UI states: loading, error_validation, error_network, success.
 *
 * @returns ReactElement
 */
export default function ForgotPasswordPage(): React.ReactElement {
  const { t } = useTranslation("auth");
  const navigate = useNavigate();

  const schema = useForgotPasswordSchema();

  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(schema),
    mode: "onTouched",
    defaultValues: { email: "" },
  });

  // ---------------------------------------------------------------------------
  // Success state — shown inline after 200 response (anti-enum opaque copy)
  // D-T003-ANTI-ENUM-UI: identical success copy for known and unknown emails.
  // ---------------------------------------------------------------------------

  const [showSuccess, setShowSuccess] = useState(false);

  // ---------------------------------------------------------------------------
  // Repository (non-injectable in prod; injectable in tests via wrapper)
  // ---------------------------------------------------------------------------

  const repo = useMemo(() => new AuthRepository(() => void 0), []);

  const onSuccess = useCallback(
    (_outcome: ForgotPasswordOutcome) => {
      // D-T003-SUCCESS-REDIRECT: navigate to /auth/reset-sent with email in router state.
      // The email is the user-typed email — NOT confirmation of DB existence (anti-enum).
      // D-T003-MASK-EMAIL: pass typed email so T004 ResetSentPage can show masked address.
      const typedEmail = getValues("email");

      logVerbose("auth.forgot.page.submit.success_navigate", {
        // PII: log only domain, not full email
        email_domain: typedEmail.includes("@") ? typedEmail.split("@")[1] : "unknown",
      });

      // Show inline success first, then navigate (T004 may not exist yet)
      setShowSuccess(true);

      // Navigate to reset-sent — T004 will render it; catch-all redirects to / if not.
      navigate(ROUTE_AUTH_RESET_SENT, {
        replace: false,
        state: { email: typedEmail },
      });
    },
    [navigate, getValues],
  );

  const {
    submit,
    isLoading,
    error: forgotError,
    clearError,
  } = useForgotPassword(repo, onSuccess);

  // ---------------------------------------------------------------------------
  // Form submit handler
  // ---------------------------------------------------------------------------

  const onSubmit = useCallback(
    async (values: ForgotPasswordFormValues) => {
      logVerbose("auth.forgot.page.submit.start", {
        email_domain: values.email.includes("@") ? values.email.split("@")[1] : "unknown",
        email_local_len: values.email.indexOf("@") >= 0 ? values.email.indexOf("@") : values.email.length,
      });
      clearError();

      const outcome = await submit({ email: values.email });

      if (!outcome) {
        logWarn("auth.forgot.page.submit.failed");
      }
    },
    [submit, clearError],
  );

  // ---------------------------------------------------------------------------
  // Error mapping for UI display
  // ---------------------------------------------------------------------------

  const serverErrorInfo = forgotError ? getForgotErrorI18nKey(forgotError) : null;
  const serverErrorText = serverErrorInfo
    ? t(serverErrorInfo.key, serverErrorInfo.interpolation as Record<string, string>)
    : null;

  const isRateLimited = forgotError instanceof ForgotPasswordRateLimitedError;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  logVerbose("auth.forgot.page.render.start", { isLoading, hasError: Boolean(forgotError), showSuccess });

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
        {t("forgot.titleHint")}
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
        {t("forgot.title")}
      </p>

      {/* Success state — opaque, anti-enumeration (§D-T003-ANTI-ENUM-UI) */}
      {showSuccess && (
        <div
          role="status"
          aria-live="polite"
          data-testid="forgot-success"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.9375rem",
            color: "var(--color-ink)",
            borderBottom: "2px solid var(--color-ink)",
            padding: "0.75rem 0",
            marginBottom: "1.25rem",
          }}
        >
          {t("forgot.successFlash")}
        </div>
      )}

      {/* Form-level error region (error_validation, error_network) */}
      {serverErrorText && !showSuccess && (
        <div
          role="alert"
          aria-live="polite"
          data-testid="forgot-form-error"
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

      {/* Forgot-password form */}
      <form
        onSubmit={handleSubmit(onSubmit)}
        noValidate
        aria-label={t("forgot.title")}
        style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}
      >
        <EditorialInput
          label={t("forgot.email")}
          type="email"
          autoComplete="username"
          placeholder={t("forgot.emailPlaceholder")}
          disabled={isLoading}
          errorMessage={errors.email?.message}
          data-testid="forgot-email-input"
          {...register("email")}
        />

        <div style={{ marginTop: "0.5rem" }}>
          <SolidCTA
            type="submit"
            loading={isLoading}
            disabled={isRateLimited}
            loadingLabel={t("forgot.status.submitting")}
            aria-busy={isLoading ? "true" : undefined}
            data-testid="forgot-submit-button"
          >
            {t("forgot.submit")}
          </SolidCTA>
        </div>
      </form>

      {/* Secondary navigation link — D-T003-ROUTER */}
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
          data-testid="forgot-link-signin"
        >
          {t("forgot.actions.signIn")}
        </Link>
      </nav>
    </MobileFrame>
  );
}

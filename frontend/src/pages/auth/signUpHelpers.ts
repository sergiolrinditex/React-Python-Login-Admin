/**
 * Hilo People — SignUpPage helpers: schema + error mapper.
 *
 * Slice/Phase: P03-S01-T002 — SignUpPage (registro email/password editorial móvil) / Phase 3.
 *
 * Responsibility: Co-located helper module for SignUpPage.tsx.
 *   Extracted to keep SignUpPage.tsx within the ~300 LoC self-contained limit
 *   (D-T002-PROACTIVE-EXTRACT — applied preemptively at 367 eff. lines).
 *
 * Contains:
 *   - useSignUpSchema(): memoized zod schema for the sign-up form.
 *   - getSignUpErrorI18nKey(): maps typed domain errors to i18n keys + UI states.
 *
 * Clean Architecture: this is the PRESENTATION layer.
 *   No business logic, no fetch calls. Only UI-mapping utilities.
 *
 * Dependencies: zod, react-i18next, auth data/errors.
 */

import { useMemo } from "react";
import { z } from "zod";
import { useTranslation } from "react-i18next";

import {
  NonCorporateEmailError,
  LegalNotAcceptedError,
  EmailTakenError,
  PasswordPolicyError,
  SignupRateLimitedError,
  NetworkError,
} from "@/features/auth/data/errors";

// ---------------------------------------------------------------------------
// Zod schema (D-T002-PASSWORD-PRE-VALIDATE, D-T002-LEGAL-LITERAL-TRUE)
// ---------------------------------------------------------------------------

/**
 * Memoized zod schema for the sign-up form.
 *
 * Client-side mirrors server policy: min 12, ≥1 letter, ≥1 digit (D-T002-PASSWORD-PRE-VALIDATE).
 * Server is still the final authority; this provides immediate UX feedback.
 *
 * D-T002-LEGAL-LITERAL-TRUE: boolean().refine(v => v === true) so unchecked checkbox
 *   shows a field error before the user even hits submit.
 * D-T002-EMAIL-CORP: zod .email() only; no domain allowlist in client
 *   (server handles via CORPORATE_EMAIL_DOMAINS env var).
 */
export function useSignUpSchema() {
  const { t } = useTranslation("auth");
  return useMemo(
    () =>
      z.object({
        email: z
          .string()
          .min(1, t("signUp.errors.emailRequired"))
          .email(t("signUp.errors.emailFormat")),
        full_name: z
          .string()
          .min(1, t("signUp.errors.fullNameRequired"))
          .max(200, t("signUp.errors.fullNameTooLong"))
          .transform((s) => s.trim()),
        password: z
          .string()
          .min(1, t("signUp.errors.passwordRequired"))
          .min(12, t("signUp.errors.passwordTooShort"))
          .max(256, t("signUp.errors.passwordPolicy"))
          .refine((pw) => /[a-zA-Z]/.test(pw), t("signUp.errors.passwordPolicy"))
          .refine((pw) => /[0-9]/.test(pw), t("signUp.errors.passwordPolicy")),
        legal_acceptance: z
          .boolean()
          .refine((v) => v === true, t("signUp.errors.legalRequired")),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
}

/** Form values type derived from the schema. */
export type SignUpFormValues = {
  email: string;
  full_name: string;
  password: string;
  legal_acceptance: boolean;
};

// ---------------------------------------------------------------------------
// Error mapper
// ---------------------------------------------------------------------------

/** Maps a sign-up error to the correct UI state and i18n key. */
export type SignUpErrorInfo = {
  key: string;
  interpolation?: Record<string, string | number>;
  state: "error_validation" | "permission_denied" | "error_network";
};

/**
 * Maps a typed domain error from useSignUp to the correct i18n key and UI state.
 *
 * D-T002-409-NO-FIELD: EmailTakenError maps to generic copy with no email field highlight.
 * D-T002-PII-LOGGING: this mapper only maps error types, never logs PII.
 *
 * @param err - Typed error from the hook's error state.
 * @returns SignUpErrorInfo with i18n key, optional interpolation, and UI state.
 */
export function getSignUpErrorI18nKey(err: Error): SignUpErrorInfo {
  if (err instanceof NonCorporateEmailError) {
    return { key: "signUp.errors.nonCorporateEmail", state: "permission_denied" };
  }
  if (err instanceof LegalNotAcceptedError) {
    return { key: "signUp.errors.legalNotAccepted", state: "error_validation" };
  }
  if (err instanceof EmailTakenError) {
    // D-T002-409-NO-FIELD: generic copy, no email field highlight (anti-enumeration)
    return { key: "signUp.errors.emailTaken", state: "error_validation" };
  }
  if (err instanceof PasswordPolicyError) {
    return { key: "signUp.errors.passwordPolicy", state: "error_validation" };
  }
  if (err instanceof SignupRateLimitedError) {
    return {
      key: "signUp.errors.rateLimited",
      interpolation: { seconds: err.retryAfter },
      state: "permission_denied",
    };
  }
  if (err instanceof NetworkError) {
    return { key: "signUp.errors.network", state: "error_network" };
  }
  return { key: "signUp.errors.serverInternal", state: "error_network" };
}

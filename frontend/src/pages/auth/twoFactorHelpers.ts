/**
 * Hilo People — TwoFactor page helpers: zod schema + error mapper.
 *
 * Slice/Phase: P03-S01-T005 — TwoFactorPage (/auth/2fa editorial móvil) / Phase 3.
 *   §D-T005-FILESIZE-PROACTIVE: extracted from TwoFactorPage.tsx to keep it ≤300 substantive lines.
 *
 * Responsibility: Pure helpers consumed by TwoFactorPage.tsx.
 *   1. useTwoFactorSchema — returns the memoized zod schema for the 6-digit code input.
 *   2. getErrorInfo — maps a domain error to i18n key + UI state + optional interpolation.
 *
 * No React component logic here — layout and effects remain in TwoFactorPage.tsx.
 *
 * Dependencies: zod, react-i18next, domain error classes.
 */

import { useMemo } from "react";
import { z } from "zod";
import { useTranslation } from "react-i18next";
import { MfaChallengeExpiredError, MfaVerifyRateLimitedError, NetworkError } from "@/features/auth/data/errors";

// ---------------------------------------------------------------------------
// Zod schema hook — 6-digit numeric code validation
// ---------------------------------------------------------------------------

/**
 * Returns the memoized zod schema for the 2FA code form.
 * Memoized per component lifecycle to avoid re-creation on render.
 *
 * @returns z.ZodObject with a `code` field (string, 6-digit pattern)
 */
export function useTwoFactorSchema() {
  const { t } = useTranslation("auth");
  return useMemo(
    () =>
      z.object({
        code: z
          .string()
          .min(1, t("twoFactor.errors.codeRequired"))
          .regex(/^\d{6}$/, t("twoFactor.errors.codeFormat")),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
}

/** Form values type for the 2FA form. */
export type TwoFactorFormValues = { code: string };

// ---------------------------------------------------------------------------
// Error info mapper
// ---------------------------------------------------------------------------

/** Error info shape returned by getErrorInfo. */
export interface TwoFactorErrorInfo {
  key: string;
  interpolation?: Record<string, string | number>;
  state: "error_validation" | "permission_denied" | "error_network";
}

/**
 * Maps a typed domain error from useVerifyMfa to the correct i18n key and UI state.
 *
 * §D-T005-AGGREGATE-401: MfaCodeInvalidError + MfaPayloadInvalidError → same error_validation bucket.
 * One copy for all 401 variants — UI must NOT branch on internal failure modes.
 *
 * @param err - The domain error from useVerifyMfa.
 * @returns TwoFactorErrorInfo with i18n key, optional interpolation, and UI state.
 */
export function getErrorInfo(err: Error): TwoFactorErrorInfo {
  if (err instanceof MfaChallengeExpiredError) {
    return { key: "twoFactor.errors.challengeExpired", state: "permission_denied" };
  }
  if (err instanceof MfaVerifyRateLimitedError) {
    return {
      key: "twoFactor.errors.rateLimited",
      interpolation: { seconds: err.retryAfter },
      state: "permission_denied",
    };
  }
  if (err instanceof NetworkError) {
    return { key: "twoFactor.errors.network", state: "error_network" };
  }
  // MfaCodeInvalidError, MfaPayloadInvalidError (all mapped to invalidCode — anti-enum)
  // MfaVerifyInternalError → serverInternal
  const errName = err.name ?? "";
  if (errName === "MfaVerifyInternalError") {
    return { key: "twoFactor.errors.serverInternal", state: "error_network" };
  }
  // §D-T005-AGGREGATE-401: ONE copy for all remaining code-related errors
  return { key: "twoFactor.errors.invalidCode", state: "error_validation" };
}

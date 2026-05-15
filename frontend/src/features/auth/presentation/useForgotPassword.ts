/**
 * Hilo People — useForgotPassword hook.
 *
 * Slice/Phase: P03-S01-T003 — ForgotPasswordPage (recuperación de acceso editorial móvil) / Phase 3.
 *
 * Responsibility: Presentation-layer hook that orchestrates the forgot-password flow.
 *   Wraps authRepository.forgotPassword() with loading/error state management.
 *   On success (200): calls onSuccess(outcome) so the page can navigate to /auth/reset-sent.
 *   Returns the submit callback + reactive state for ForgotPasswordPage consumption.
 *
 * Clean Architecture: this is the PRESENTATION layer (§D-T003-USEFORGOT).
 *   Depends on IAuthRepository port (not concrete class).
 *   Consumed only by ForgotPasswordPage — not exported for general use beyond barrel.
 *
 * Anti-enumeration invariant (§D-T003-ANTI-ENUM-UI):
 *   The server returns 200 for ALL valid email syntax inputs, regardless of whether
 *   the email exists. onSuccess is called for BOTH known and unknown emails.
 *   UI must never distinguish these cases — always show the identical success state.
 *
 * Decision log:
 *   D-T003-USEFORGOT: extracted for testability and to keep ForgotPasswordPage ≤300 LoC.
 *   D-T003-PII-LOGGING: email_domain + email_local_len only; NEVER log full email.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR via logger.ts.
 * Security: NEVER log full email, password, or PII. Log email_domain only.
 */

import { useState, useCallback } from "react";
import type { ForgotPasswordRequest, ForgotPasswordOutcome } from "../domain/AuthRepository";
import type { IAuthRepository } from "../domain/AuthRepository";
import type {
  ForgotPasswordValidationError,
  ForgotPasswordRateLimitedError,
  ForgotPasswordInternalError,
} from "../data/errors";
import { NetworkError } from "../data/errors";
import { logVerbose, logWarn, logError } from "../data/logger";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** All error types that can result from a forgot-password attempt. */
export type ForgotPasswordError =
  | InstanceType<typeof ForgotPasswordValidationError>
  | InstanceType<typeof ForgotPasswordRateLimitedError>
  | InstanceType<typeof ForgotPasswordInternalError>
  | InstanceType<typeof NetworkError>
  | Error;

/**
 * Return value of useForgotPassword.
 * submit: async function — call with the ForgotPasswordRequest.
 * isLoading: true while request in flight.
 * error: last error, or null.
 * clearError: resets error state.
 */
export interface UseForgotPasswordReturn {
  submit: (req: ForgotPasswordRequest) => Promise<ForgotPasswordOutcome | null>;
  isLoading: boolean;
  error: ForgotPasswordError | null;
  clearError: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Forgot-password orchestration hook.
 *
 * @param repo - IAuthRepository implementation (injectable for tests).
 * @param onSuccess - Callback when forgot-password succeeds (200); receives ForgotPasswordOutcome.
 *   Also called for unknown emails (anti-enumeration invariant).
 *   Provided by ForgotPasswordPage to trigger navigation to /auth/reset-sent.
 * @returns UseForgotPasswordReturn
 */
export function useForgotPassword(
  repo: IAuthRepository,
  onSuccess: (outcome: ForgotPasswordOutcome) => void,
): UseForgotPasswordReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ForgotPasswordError | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const submit = useCallback(
    async (req: ForgotPasswordRequest): Promise<ForgotPasswordOutcome | null> => {
      // BEFORE log — §D-T003-PII-LOGGING: email_domain + email_local_len only
      const atIdx = req.email.indexOf("@");
      const emailDomain = atIdx >= 0 ? req.email.slice(atIdx + 1) : "unknown";
      const emailLocalLen = atIdx >= 0 ? atIdx : req.email.length;

      logVerbose("auth.forgot.hook.submit.start", {
        email_domain: emailDomain,
        email_local_len: emailLocalLen,
      });

      setIsLoading(true);
      setError(null);

      try {
        const result = await repo.forgotPassword(req);

        if (!result.ok) {
          // WARN on error — log error name only (no PII)
          logWarn("auth.forgot.hook.submit.error", { error_name: result.error.name });
          setError(result.error as ForgotPasswordError);
          return null;
        }

        // AFTER log — sent is non-PII
        logVerbose("auth.forgot.hook.submit.ok", { sent: result.value.sent });

        onSuccess(result.value);
        return result.value;
      } catch (err: unknown) {
        const domainErr = err instanceof Error ? err : new Error("Unknown forgot-password error");
        logError("auth.forgot.hook.submit.unexpected", { error: domainErr.message });
        setError(domainErr);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [repo, onSuccess],
  );

  return { submit, isLoading, error, clearError };
}

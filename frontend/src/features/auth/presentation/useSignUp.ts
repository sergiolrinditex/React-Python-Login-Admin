/**
 * Hilo People — useSignUp hook.
 *
 * Slice/Phase: P03-S01-T002 — SignUpPage (registro email/password editorial móvil) / Phase 3.
 *
 * Responsibility: Presentation-layer hook that orchestrates the sign-up flow.
 *   Wraps authRepository.signUp() with loading/error state management.
 *   On success (201): calls onSuccess(outcome) so the page can navigate.
 *   Returns the submit callback + reactive state for SignUpPage consumption.
 *
 * Clean Architecture: this is the PRESENTATION layer.
 *   Depends on IAuthRepository port (not concrete class).
 *   Consumed only by SignUpPage — not exported for general use beyond barrel.
 *
 * Decision log (§15 of task pack):
 *   D-T002-USESIGNUP: extracted for testability and to keep SignUpPage ≤300 LoC.
 *   D-T002-PII-LOGGING: email_domain only; NEVER log full email, password, full_name.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR via logger.ts.
 * Security: NEVER log password. NEVER log full email or full_name (PII).
 */

import { useState, useCallback } from "react";
import type { SignUpRequest, SignUpOutcome } from "../domain/AuthRepository";
import type { IAuthRepository } from "../domain/AuthRepository";
import type {
  NonCorporateEmailError,
  LegalNotAcceptedError,
  EmailTakenError,
  PasswordPolicyError,
  SignupRateLimitedError,
  SignupValidationError,
  SignupInternalError,
} from "../data/errors";
import { NetworkError } from "../data/errors";
import { logVerbose, logWarn, logError } from "../data/logger";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** All error types that can result from a sign-up attempt. */
export type SignUpError =
  | InstanceType<typeof NonCorporateEmailError>
  | InstanceType<typeof LegalNotAcceptedError>
  | InstanceType<typeof EmailTakenError>
  | InstanceType<typeof PasswordPolicyError>
  | InstanceType<typeof SignupRateLimitedError>
  | InstanceType<typeof SignupValidationError>
  | InstanceType<typeof SignupInternalError>
  | InstanceType<typeof NetworkError>
  | Error;

/**
 * Return value of useSignUp.
 * submit: async function — call with the full SignUpRequest.
 * isLoading: true while request in flight.
 * error: last error, or null.
 * clearError: resets error state.
 */
export interface UseSignUpReturn {
  submit: (req: SignUpRequest) => Promise<SignUpOutcome | null>;
  isLoading: boolean;
  error: SignUpError | null;
  clearError: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Sign-up orchestration hook.
 *
 * @param repo - IAuthRepository implementation (injectable for tests).
 * @param onSuccess - Callback when sign-up succeeds (201); receives SignUpOutcome.
 *   Provided by the calling page (SignUpPage) to trigger navigation.
 * @returns UseSignUpReturn
 */
export function useSignUp(
  repo: IAuthRepository,
  onSuccess: (outcome: SignUpOutcome) => void,
): UseSignUpReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<SignUpError | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const submit = useCallback(
    async (req: SignUpRequest): Promise<SignUpOutcome | null> => {
      // BEFORE log — D-T002-PII-LOGGING: email_domain only, password_len numeric
      logVerbose("auth.signup.hook.submit.start", {
        email_domain: req.email.includes("@") ? req.email.split("@")[1] : "unknown",
        password_len: req.password.length,
        has_full_name: req.full_name.trim().length > 0,
        legal_accepted: req.legal_acceptance,
      });

      setIsLoading(true);
      setError(null);

      try {
        const result = await repo.signUp(req);

        if (!result.ok) {
          // WARN on error — log error name only (no PII)
          logWarn("auth.signup.hook.submit.error", { error_name: result.error.name });
          setError(result.error as SignUpError);
          return null;
        }

        // AFTER log — user_id is a UUID (non-PII, safe to log)
        logVerbose("auth.signup.hook.submit.ok", {
          user_id: result.value.user_id,
          mfa_required: result.value.mfa_required,
        });

        onSuccess(result.value);
        return result.value;
      } catch (err: unknown) {
        const domainErr = err instanceof Error ? err : new Error("Unknown sign-up error");
        logError("auth.signup.hook.submit.unexpected", { error: domainErr.message });
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

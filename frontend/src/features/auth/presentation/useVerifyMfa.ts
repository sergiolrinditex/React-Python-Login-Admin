/**
 * Hilo People — useVerifyMfa hook.
 *
 * Slice/Phase: P03-S01-T005 — TwoFactorPage (/auth/2fa editorial móvil) / Phase 3.
 *
 * Responsibility: Presentation-layer hook that orchestrates the MFA verify flow.
 *   Wraps authRepository.verifyMfa() with loading/error state management.
 *   On success: calls signInAccepted(accessToken, user) from AuthProvider.
 *   Returns the submit callback + reactive state for TwoFactorPage consumption.
 *
 * Clean Architecture: this is the PRESENTATION layer. §D-T005-USEVERIFYMFA.
 *   Depends on IAuthRepository port (not concrete class).
 *   Consumed only by TwoFactorPage — not exported for general use beyond barrel.
 *
 * Decision log:
 *   D-T005-USEVERIFYMFA: extracted for testability, keeps TwoFactorPage ≤300 LoC.
 *   D-T005-AGGREGATE-401: MfaCodeInvalidError wraps the aggregate 401 (no UI branching).
 *   D-T005-PII-LOGGING: only code_len, challenge_token_len, request_id in logs.
 *   D-T005-EXPIRED-CHALLENGE: on MfaChallengeExpiredError, caller (the page) auto-redirects.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR via logger.ts.
 * Security: NEVER log code, challengeToken, full email, or access token.
 */

import { useState, useCallback } from "react";
import type { VerifyMfaRequest, VerifyMfaOutcome } from "../domain/AuthRepository";
import type { IAuthRepository } from "../domain/AuthRepository";
import type {
  MfaPayloadInvalidError,
  MfaCodeInvalidError,
  MfaChallengeExpiredError,
  MfaVerifyRateLimitedError,
  MfaVerifyInternalError,
} from "../data/errors";
import { NetworkError } from "../data/errors";
import { logVerbose, logWarn, logError } from "../data/logger";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** All error types that can result from a verifyMfa attempt. */
export type VerifyMfaError =
  | InstanceType<typeof MfaPayloadInvalidError>
  | InstanceType<typeof MfaCodeInvalidError>
  | InstanceType<typeof MfaChallengeExpiredError>
  | InstanceType<typeof MfaVerifyRateLimitedError>
  | InstanceType<typeof MfaVerifyInternalError>
  | InstanceType<typeof NetworkError>
  | Error;

/**
 * Return value of useVerifyMfa.
 * submit: async function — call with {challengeToken, code}.
 * isLoading: true while request in flight.
 * error: last error, or null.
 * clearError: resets error state.
 */
export interface UseVerifyMfaReturn {
  submit: (req: VerifyMfaRequest) => Promise<VerifyMfaOutcome | null>;
  isLoading: boolean;
  error: VerifyMfaError | null;
  clearError: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * MFA verify orchestration hook.
 *
 * Client-side validation:
 *   - challengeToken must be present (non-empty).
 *   - code must be exactly 6 digits (pre-validated in TwoFactorPage via zod, but
 *     this hook returns null without calling the repo if code length ≠ 6 as defence).
 *
 * @param repo - IAuthRepository implementation (injectable for tests).
 * @param onSuccess - Callback when MFA verify succeeds; receives accessToken + user.
 *   Provided by AuthProvider via signInAccepted — sets authenticated session state.
 * @returns UseVerifyMfaReturn
 */
export function useVerifyMfa(
  repo: IAuthRepository,
  onSuccess: (accessToken: string, user: import("../domain/types").UserProfile) => void,
): UseVerifyMfaReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<VerifyMfaError | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const submit = useCallback(
    async (req: VerifyMfaRequest): Promise<VerifyMfaOutcome | null> => {
      // §D-T005-PII-LOGGING: only lengths, never values
      logVerbose("auth.mfa.verify.hook.submit.start", {
        challenge_token_len: req.challengeToken.length,
        code_len: req.code.length,
      });

      // Guard: challengeToken must be present
      if (!req.challengeToken) {
        logWarn("auth.mfa.verify.hook.submit.missing_challenge");
        return null;
      }

      // Guard: code must be exactly 6 digits (defence in depth; zod handles in page)
      if (!/^\d{6}$/.test(req.code)) {
        logWarn("auth.mfa.verify.hook.submit.invalid_code_format", {
          code_len: req.code.length,
        });
        return null;
      }

      setIsLoading(true);
      setError(null);

      try {
        const result = await repo.verifyMfa(req);

        if (!result.ok) {
          logWarn("auth.mfa.verify.hook.submit.error", {
            error_name: result.error.name,
            error_code: (result.error as { code?: string }).code,
          });
          setError(result.error as VerifyMfaError);
          return null;
        }

        const outcome = result.value;
        logVerbose("auth.mfa.verify.hook.submit.ok", {
          token_len: outcome.accessToken.length,
          expires_in: outcome.expiresIn,
          user_id: outcome.user.id,
        });

        // Notify AuthProvider → sets authenticated session state
        onSuccess(outcome.accessToken, outcome.user);

        return outcome;
      } catch (err: unknown) {
        const domainErr = err instanceof Error ? err : new Error("Unknown MFA verify error");
        logError("auth.mfa.verify.hook.submit.unexpected", { error: domainErr.message });
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

/**
 * Hilo People — useSignIn hook.
 *
 * Slice/Phase: P03-S01-T001 — SignInPage (Login email/password editorial móvil) / Phase 3.
 *
 * Responsibility: Presentation-layer hook that orchestrates the sign-in flow.
 *   Wraps authRepository.signIn() with loading/error state management.
 *   On success (no-MFA): calls signInAccepted(token, user) from AuthProvider.
 *   Returns the submit callback + reactive state for SignInPage consumption.
 *
 * Clean Architecture: this is the PRESENTATION layer.
 *   Depends on IAuthRepository port (not concrete class).
 *   Consumed only by SignInPage — not exported for general use.
 *
 * Decision log (§9 of task pack):
 *   D-T001-USESIGNIN: extracted to keep SignInPage ≤300 LoC self-contained.
 *   D-T001-USERFETCH-ON-SUCCESS: no-MFA branch calls fetchMe inside signIn() impl.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR via logger.ts.
 * Security: NEVER log password. NEVER log full token.
 */

import { useState, useCallback } from "react";
import type { SignInRequest, SignInOutcome } from "../domain/AuthRepository";
import type { IAuthRepository } from "../domain/AuthRepository";
import type {
  InvalidCredentialsError,
  AccountLockedError,
  RateLimitedError,
  SigninValidationError,
  SigninInternalError,
} from "../data/errors";
import { NetworkError } from "../data/errors";
import { logVerbose, logWarn, logError } from "../data/logger";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** All error types that can result from a sign-in attempt. */
export type SignInError =
  | InstanceType<typeof InvalidCredentialsError>
  | InstanceType<typeof AccountLockedError>
  | InstanceType<typeof RateLimitedError>
  | InstanceType<typeof SigninValidationError>
  | InstanceType<typeof SigninInternalError>
  | InstanceType<typeof NetworkError>
  | Error;

/**
 * Return value of useSignIn.
 * submit: async function — call with {email, password}.
 * isLoading: true while request in flight.
 * error: last error, or null.
 * clearError: resets error state.
 */
export interface UseSignInReturn {
  submit: (req: SignInRequest) => Promise<SignInOutcome | null>;
  isLoading: boolean;
  error: SignInError | null;
  clearError: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Sign-in orchestration hook.
 *
 * @param repo - IAuthRepository implementation (injectable for tests).
 * @param onSuccess - Callback when sign-in succeeds (no-MFA); receives token + user.
 *   Provided by AuthProvider via signInAccepted.
 * @returns UseSignInReturn
 */
export function useSignIn(
  repo: IAuthRepository,
  onSuccess: (accessToken: string, user: import("../domain/types").UserProfile) => void,
): UseSignInReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<SignInError | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const submit = useCallback(
    async (req: SignInRequest): Promise<SignInOutcome | null> => {
      logVerbose("auth.signin.hook.submit.start", {
        email_domain: req.email.includes("@") ? req.email.split("@")[1] : "unknown",
        password_len: req.password.length,
      });

      setIsLoading(true);
      setError(null);

      try {
        const result = await repo.signIn(req);

        if (!result.ok) {
          logWarn("auth.signin.hook.submit.error", { error_name: result.error.name });
          setError(result.error as SignInError);
          return null;
        }

        const outcome = result.value;

        if (outcome.kind === "success") {
          logVerbose("auth.signin.hook.submit.ok_no_mfa", {
            token_len: outcome.accessToken.length,
          });
          onSuccess(outcome.accessToken, outcome.user);
        } else {
          logVerbose("auth.signin.hook.submit.mfa_required", {
            challenge_token_len: outcome.challengeToken.length,
            expires_in: outcome.expiresIn,
          });
        }

        return outcome;
      } catch (err: unknown) {
        const domainErr = err instanceof Error ? err : new Error("Unknown sign-in error");
        logError("auth.signin.hook.submit.unexpected", { error: domainErr.message });
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

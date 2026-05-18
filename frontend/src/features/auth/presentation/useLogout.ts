/**
 * Hilo People — useLogout hook.
 *
 * Slice/Phase: P03-S02-T007 — AccountPage (profile + language + logout) / Phase 3.
 *
 * Responsibility: Thin presentation hook that wraps AuthProvider.logout() with
 *   isLoggingOut state and navigation to /auth/sign-in after completion.
 *
 * Clean Architecture: PRESENTATION layer. Delegates actual auth logic to
 *   AuthProvider.logout() (which calls authRepository.logout() internally).
 *   No direct import of AuthRepository — depends on the useAuth() port.
 *
 * Defensive logout invariant (§D-T007-DEFENSIVE-LOGOUT):
 *   - AuthProvider.logout() ALWAYS clears access token and local state, even if
 *     backend returns 401 or a network error occurs (pre-existing behavior in AuthProvider).
 *   - useLogout navigates to /auth/sign-in REGARDLESS of AuthProvider.logout() outcome.
 *   - This hook never blocks navigation on error — the UI must always reach sign-in.
 *
 * Logging contract (non-negotiables §logging):
 *   BEFORE: auth.logout.start (no payload — token never logged).
 *   AFTER OK: auth.logout.ok (request_id from AuthProvider).
 *   AFTER ERR: auth.logout.error (error.message — never PII).
 *   Gated by VITE_ENABLE_VERBOSE_LOGGING.
 *
 * §D-T007-NAVBAR-DEFERRED: no navbar link in this slice (write_set excludes chat shell).
 * Verification navigates to /account via direct URL. See handoff §D-T007-NAVBAR-DEFERRED.
 *
 * Key deps: react, react-router, AuthProvider (useAuth), logger.
 */

import { useState, useCallback } from "react";
import { useNavigate } from "react-router";
import { useAuth } from "./AuthProvider";
import { logVerbose, logError } from "../data/logger";
import { ROUTE_AUTH_SIGN_IN } from "../../../app/router";

// ---------------------------------------------------------------------------
// Return type
// ---------------------------------------------------------------------------

/**
 * Return value of useLogout.
 *
 * @property logout - Call to trigger the logout flow. Navigates to /auth/sign-in.
 * @property isLoggingOut - True while the logout request is in flight.
 * @property error - Non-null if logout encountered a network error (navigation still
 *   happens, but consumer may display a brief error message before redirect).
 */
export interface UseLogoutReturn {
  logout: () => Promise<void>;
  isLoggingOut: boolean;
  error: Error | null;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * useLogout hook — wraps AuthProvider.logout() with loading state + navigation.
 *
 * Defensive invariant: ALWAYS navigates to /auth/sign-in, even on error.
 * AuthProvider.logout() clears token + state before this hook's navigation fires.
 *
 * @returns UseLogoutReturn
 */
export function useLogout(): UseLogoutReturn {
  const { logout: providerLogout } = useAuth();
  const navigate = useNavigate();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const logout = useCallback(async (): Promise<void> => {
    logVerbose("auth.logout.start");
    setIsLoggingOut(true);
    setError(null);

    try {
      await providerLogout();
      logVerbose("auth.logout.ok");
    } catch (err: unknown) {
      const domainErr = err instanceof Error ? err : new Error("Logout failed unexpectedly");
      logError("auth.logout.error", { error: domainErr.message });
      setError(domainErr);
      // Defensive: ALWAYS navigate even on error (token already cleared by AuthProvider)
    } finally {
      setIsLoggingOut(false);
    }

    // Navigate after finally so isLoggingOut is false before route change
    void navigate(ROUTE_AUTH_SIGN_IN, { replace: true });
  }, [providerLogout, navigate]);

  return { logout, isLoggingOut, error };
}

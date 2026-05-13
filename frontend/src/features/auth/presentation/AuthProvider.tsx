/**
 * Hilo People — AuthProvider: auth state context for the application.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *
 * Responsibility: React context provider that manages authentication state.
 *   - On mount: calls POST /api/v1/auth/refresh to rehydrate from HttpOnly cookie.
 *   - Exposes useAuth() hook for all consumers.
 *   - Exposes signInAccepted(token, user) for the SignInPage (P03-S01-T001) to call
 *     after successful sign-in, avoiding a redundant /me round-trip.
 *   - Wires AuthRepository with an onAuthFailure callback that resets state to
 *     'unauthenticated' and clears the access token store.
 *
 * Composition rule (providers.tsx docstring, task pack §I):
 *   AuthProvider is wired INSIDE router.tsx (not in providers.tsx).
 *   The QueryClient is above AuthProvider; auth hooks may invalidate queries.
 *
 * Status lifecycle:
 *   hydrating → authenticated   (refresh + /me succeeded on mount)
 *   hydrating → unauthenticated (refresh returned 401 or network error)
 *   authenticated → unauthenticated (onAuthFailure triggered by 401 interceptor)
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR via logger.ts.
 * Security: NEVER log token value. NEVER log user.email. Log user.id only.
 */

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useMemo,
  type ReactNode,
} from "react";
import type { AuthSession, UserProfile } from "../domain/types";
import { AuthRepository } from "../data/authRepository";
import { setAccessToken, clearAccessToken, getAccessToken } from "../data/accessTokenStore";
import { logVerbose, logWarn, logError } from "../data/logger";

// ---------------------------------------------------------------------------
// Auth context type
// ---------------------------------------------------------------------------

/**
 * Shape exposed by useAuth().
 * All fields are stable references (memoized via useMemo/useCallback).
 */
export interface AuthContextValue extends AuthSession {
  /**
   * Called by SignInPage (P03-S01-T001) after a successful sign-in.
   * Accepts the access token and user profile, avoids a redundant /me call.
   *
   * @param accessToken - Opaque access token from sign-in response.
   * @param user - UserProfile from sign-in response.
   */
  signInAccepted: (accessToken: string, user: UserProfile) => void;

  /**
   * Triggers a logout: calls /logout, clears token + queries, sets unauthenticated.
   * Side effects run EVEN IF backend returns 401 (defensive logout — task pack §P #9).
   */
  logout: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// Context (internal — consumers use useAuth())
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextValue | null>(null);

// ---------------------------------------------------------------------------
// AuthProvider component
// ---------------------------------------------------------------------------

/**
 * Application auth state provider.
 *
 * Wrap the route tree (inside BrowserRouter) with this provider.
 * Children may call useAuth() to access auth state.
 *
 * @param children - The route tree / application shell.
 * @param _repo - Injectable repository for testing. Defaults to real AuthRepository.
 * @param _onQueriesClear - Injectable query cache clear for testing. Defaults to no-op.
 */
export function AuthProvider({
  children,
  _repo,
  _onQueriesClear,
}: {
  children: ReactNode;
  /** @internal Test injection point for the auth repository. */
  _repo?: AuthRepository;
  /** @internal Test injection for QueryClient.clear(). */
  _onQueriesClear?: () => void;
}): React.ReactElement {
  const [status, setStatus] = useState<AuthSession["status"]>("hydrating");
  const [user, setUser] = useState<UserProfile | null>(null);

  // onAuthFailure: called when 401 cannot be recovered (session fully expired)
  const onAuthFailure = useCallback(() => {
    logWarn("auth.provider.session_expired.local_cleared");
    clearAccessToken();
    setStatus("unauthenticated");
    setUser(null);
    if (_onQueriesClear) _onQueriesClear();
  }, [_onQueriesClear]);

  const repo = useMemo(
    () => _repo ?? new AuthRepository(onAuthFailure),
    [_repo, onAuthFailure],
  );

  // ---------------------------------------------------------------------------
  // Mount-time hydration: refresh → /me
  // ---------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    async function hydrate(): Promise<void> {
      logVerbose("auth.provider.hydrate.start");

      const refreshResult = await repo.refresh();

      if (cancelled) return;

      if (!refreshResult.ok) {
        logVerbose("auth.provider.hydrate.unauthenticated", {
          error: refreshResult.error.message,
        });
        setStatus("unauthenticated");
        return;
      }

      const token = refreshResult.value;
      setAccessToken(token);

      const meResult = await repo.fetchMe(token);

      if (cancelled) return;

      if (!meResult.ok) {
        logWarn("auth.provider.hydrate.me_failed", {
          error: meResult.error.message,
        });
        clearAccessToken();
        setStatus("unauthenticated");
        return;
      }

      setUser(meResult.value);
      setStatus("authenticated");
      logVerbose("auth.provider.hydrate.ok", { user_id: meResult.value.id });
    }

    hydrate().catch((err: unknown) => {
      if (cancelled) return;
      logError("auth.provider.hydrate.unexpected_error", {
        error: err instanceof Error ? err.message : String(err),
      });
      clearAccessToken();
      setStatus("unauthenticated");
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---------------------------------------------------------------------------
  // signInAccepted — called by SignInPage after successful sign-in
  // ---------------------------------------------------------------------------

  const signInAccepted = useCallback(
    (accessToken: string, newUser: UserProfile) => {
      logVerbose("auth.provider.signin_accepted", {
        user_id: newUser.id,
        token_len: accessToken.length,
      });
      setAccessToken(accessToken);
      setUser(newUser);
      setStatus("authenticated");
    },
    [],
  );

  // ---------------------------------------------------------------------------
  // Logout
  // ---------------------------------------------------------------------------

  const logout = useCallback(async (): Promise<void> => {
    logVerbose("auth.provider.logout.start");
    const token = getAccessToken();

    if (token !== null) {
      const result = await repo.logout(token);
      if (!result.ok) {
        logWarn("auth.provider.logout.failure_local_cleared", {
          error: result.error.message,
        });
      } else {
        logVerbose("auth.provider.logout.ok");
      }
    }

    // Defensive cleanup — runs EVEN IF /logout returned 401 (task pack §P #9)
    clearAccessToken();
    setStatus("unauthenticated");
    setUser(null);
    if (_onQueriesClear) _onQueriesClear();
  }, [repo, _onQueriesClear]);

  // ---------------------------------------------------------------------------
  // Context value (memoized to prevent unnecessary rerenders)
  // ---------------------------------------------------------------------------

  const contextValue = useMemo<AuthContextValue>(
    () => ({ status, user, signInAccepted, logout }),
    [status, user, signInAccepted, logout],
  );

  return (
    <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// useAuth hook
// ---------------------------------------------------------------------------

/**
 * Returns the current auth context value.
 * Must be called inside a component tree wrapped by <AuthProvider>.
 *
 * @throws Error if called outside <AuthProvider>.
 */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error(
      "[useAuth] Must be called inside <AuthProvider>. " +
        "Ensure your route tree is wrapped with <AuthProvider>.",
    );
  }
  return ctx;
}

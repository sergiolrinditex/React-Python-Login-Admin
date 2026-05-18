/**
 * Hilo People — useLanguagePicker hook.
 *
 * Slice/Phase: P03-S02-T007 — AccountPage (profile + language + logout) / Phase 3.
 *
 * Responsibility: Presentation hook that manages language switching.
 *   Wraps authRepository.updateLanguage() with optimistic i18n update + revert on error.
 *   Uses `useAuth()` to read current user (language preference) and access token.
 *
 * Clean Architecture: PRESENTATION layer. Calls authRepository.updateLanguage()
 *   (data layer) via direct repo access using the concrete AuthRepository.
 *   The AuthRepository is accessible because we need updateLanguage(), which is not
 *   on the IAuthRepository port yet (§D-T007-WRITE-SET-DRIFT-AUTHREPO).
 *
 * Optimistic update strategy (§D-T004-LANGUAGE-OPTIMISTIC mirror):
 *   1. Capture `previousLanguage` from i18n.language.
 *   2. Immediately call i18n.changeLanguage(language) (optimistic).
 *   3. Call authRepository.updateLanguage(token, language).
 *   4. On success: no revert (server confirmed).
 *   5. On error: call i18n.changeLanguage(previousLanguage) to revert.
 *
 * Concurrent switch pattern (§D-T004-LANGUAGE-OPTIMISTIC lastIntendedLanguageRef):
 *   Uses lastIntendedLanguageRef to track the latest intended language. If rapid
 *   es→en→fr sequence arrives, only the last PATCH result matters for final state.
 *   Intermediate reverts are skipped if a newer switch is in flight.
 *
 * Error states:
 *   - error_validation: 400/422 from server → message shown; i18n reverted.
 *   - error_network: fetch failure → message shown; i18n reverted.
 *   - Both are represented as the `error` field with discriminated `code`.
 *
 * Logging contract (non-negotiables §logging, VITE_ENABLE_VERBOSE_LOGGING gated):
 *   BEFORE: auth.language.update.start (from, to, request_id).
 *   AFTER OK: auth.language.update.ok (to, user_id).
 *   AFTER ERR: auth.language.update.error (error.message) + revert: auth.language.update.revert (back_to).
 *
 * Security: NEVER log token value. NEVER log email. Log user_id only.
 *
 * Key deps: react, i18next, useAuth, AuthRepository, accessTokenStore, logger.
 */

import { useState, useRef, useCallback } from "react";
import i18n from "i18next";
import type { Language } from "../../../i18n/languages";
import { SUPPORTED_LANGUAGES } from "../../../i18n/languages";
import { useAuth } from "./AuthProvider";
import { AuthRepository } from "../data/authRepository";
import { getAccessToken } from "../data/accessTokenStore";
import { logVerbose, logWarn, logError } from "../data/logger";
import { NetworkError } from "../data/errors";

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

/**
 * Error produced by useLanguagePicker.
 *
 * @property code - 'validation' for 400/422 server errors; 'network' for fetch failures.
 * @property message - User-facing error message key source (use i18n mapping).
 */
export interface LanguagePickerError {
  code: "validation" | "network";
  message: string;
}

// ---------------------------------------------------------------------------
// Return type
// ---------------------------------------------------------------------------

/**
 * Return value of useLanguagePicker.
 *
 * @property current - Current language from user profile (source of truth: useAuth().user).
 * @property setLanguage - Trigger language change (optimistic + PATCH).
 * @property isPending - True while PATCH is in flight.
 * @property error - Non-null if last change failed (validation or network).
 * @property clearError - Reset error state.
 */
export interface UseLanguagePickerReturn {
  current: Language;
  setLanguage: (language: Language) => Promise<void>;
  isPending: boolean;
  error: LanguagePickerError | null;
  clearError: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Language picker hook — optimistic language switching with server persistence.
 *
 * Reads current language from useAuth().user.preferred_language.
 * Falls back to i18n.language on null user (should not happen inside RequireAuth).
 *
 * @returns UseLanguagePickerReturn
 */
export function useLanguagePicker(): UseLanguagePickerReturn {
  const { user, logout: _authLogout } = useAuth();

  // §D-T007-D1-CONFIRMED-CURRENT (debugger cycle 1, option A):
  //   After a successful PATCH the server returns the updated UserProfile, but
  //   AuthProvider.user.preferred_language only refreshes on the next hydration
  //   (no setter exposed by AuthContext). To keep the radiogroup `aria-checked`
  //   in sync with the language that was just confirmed by the server, we keep
  //   a local `confirmedCurrent` state that is set from result.value.preferred_language
  //   on PATCH 200 success. It is NOT touched on validation/network failure (so
  //   on rollback the previous confirmed value persists).
  //   `current` is derived as: confirmedCurrent ?? user.preferred_language ?? i18n.language.
  //   This is the "setter pattern" described in the task pack §D-T007-USERREAD-CHOICE.
  const [confirmedCurrent, setConfirmedCurrent] = useState<Language | null>(null);

  // Source of truth for current language: confirmed server value > user profile > i18n.
  const fallbackFromUser: Language | null =
    user?.preferred_language && SUPPORTED_LANGUAGES.includes(user.preferred_language as Language)
      ? (user.preferred_language as Language)
      : null;
  const current: Language =
    confirmedCurrent ?? fallbackFromUser ?? ((i18n.language as Language) ?? "es");

  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<LanguagePickerError | null>(null);

  // §D-T004-LANGUAGE-OPTIMISTIC: track last intended language to handle concurrent rapid switches
  const lastIntendedRef = useRef<Language | null>(null);

  // repo instance (stable across renders — created once; onAuthFailure handled by AuthProvider)
  // Note: we use AuthRepository directly because updateLanguage is not on IAuthRepository port.
  // §D-T007-WRITE-SET-DRIFT-AUTHREPO justification: same reason as authRepository.ts itself.
  const repoRef = useRef<AuthRepository | null>(null);
  if (repoRef.current === null) {
    // onAuthFailure: no-op here; AuthProvider owns that lifecycle
    repoRef.current = new AuthRepository(() => void 0);
  }
  const repo = repoRef.current;

  const clearError = useCallback(() => setError(null), []);

  const setLanguage = useCallback(
    async (language: Language): Promise<void> => {
      if (!SUPPORTED_LANGUAGES.includes(language)) {
        logWarn("auth.language.update.invalid_language", { attempted: language });
        setError({ code: "validation", message: `Unsupported language: ${language}` });
        return;
      }

      const previousLanguage = i18n.language as Language;
      lastIntendedRef.current = language;

      const requestId = crypto.randomUUID();
      logVerbose("auth.language.update.start", {
        from: previousLanguage,
        to: language,
        request_id: requestId,
      });

      // Optimistic update
      await i18n.changeLanguage(language);
      setError(null);
      setIsPending(true);

      try {
        const token = getAccessToken();
        if (token === null) {
          logWarn("auth.language.update.no_token", { request_id: requestId });
          await i18n.changeLanguage(previousLanguage);
          setError({ code: "network", message: "No access token available" });
          return;
        }

        const result = await repo.updateLanguage(token, language);

        // Only process result if this is still the latest intended switch
        if (lastIntendedRef.current !== language) {
          logVerbose("auth.language.update.stale_ignored", {
            intended: lastIntendedRef.current,
            arrived: language,
          });
          return;
        }

        if (!result.ok) {
          const err = result.error;
          const isValidation = err.message.startsWith("LANGUAGE_INVALID");

          logError("auth.language.update.error", {
            error: err.message,
            request_id: requestId,
          });

          // Revert optimistic change
          logVerbose("auth.language.update.revert", { back_to: previousLanguage });
          await i18n.changeLanguage(previousLanguage);

          setError({
            code: isValidation ? "validation" : "network",
            message: err.message,
          });
          return;
        }

        logVerbose("auth.language.update.ok", {
          to: language,
          user_id: result.value.id,
          request_id: requestId,
        });

        // Server confirmed — promote returned preferred_language to local confirmed state
        // so `current` reflects the new value immediately (radiogroup aria-checked stays in sync).
        // §D-T007-D1-CONFIRMED-CURRENT.
        const serverLang = result.value.preferred_language;
        if (SUPPORTED_LANGUAGES.includes(serverLang as Language)) {
          setConfirmedCurrent(serverLang as Language);
        } else {
          // Defensive fallback: trust the requested language if server echo is malformed.
          setConfirmedCurrent(language);
        }
        // Note: AuthProvider.user.preferred_language will catch up on next refresh/re-hydration.
        // For immediate correctness, both i18n.language and confirmedCurrent reflect the new value.
      } catch (err: unknown) {
        if (lastIntendedRef.current !== language) return;

        const domainErr = err instanceof Error ? err : new Error("Language update failed");
        logError("auth.language.update.error", {
          error: domainErr.message,
          request_id: requestId,
        });

        logVerbose("auth.language.update.revert", { back_to: previousLanguage });
        await i18n.changeLanguage(previousLanguage);

        setError({
          code: err instanceof NetworkError ? "network" : "network",
          message: domainErr.message,
        });
      } finally {
        if (lastIntendedRef.current === language) {
          setIsPending(false);
        }
      }
    },
    [repo],
  );

  return { current, setLanguage, isPending, error, clearError };
}

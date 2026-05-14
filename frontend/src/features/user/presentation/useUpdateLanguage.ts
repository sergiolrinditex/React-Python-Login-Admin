/**
 * Hilo People — useUpdateLanguage hook.
 *
 * Slice/Phase: P03-S02-T004 — AccountPage / Phase 3.
 *
 * Responsibility: TanStack Query useMutation for PATCH /api/v1/users/me/language.
 *   Implements the optimistic language swap (§D-T004-LANGUAGE-OPTIMISTIC):
 *     1. On mutate: immediately call i18n.changeLanguage(newLang) + update query cache.
 *     2. On error: revert i18n.changeLanguage(prevLang) + rollback query cache.
 *     3. On settled: invalidate ["user","me"] to fetch authoritative profile.
 *
 * Race guard (§R1 + §D-T004-LANGUAGE-OPTIMISTIC):
 *   A lastIntendedLanguageRef tracks which language the user last clicked.
 *   If a stale onSuccess fires after a newer mutation started, it is ignored
 *   (checked via ref before applying the settled result).
 *
 * i18n side-effect:
 *   i18n.changeLanguage() is the ONLY place that changes the active locale.
 *   Called synchronously in onMutate (optimistic) and reverted in onError.
 *
 * Security: NEVER log access tokens. Language code (es/en/fr) is safe to log.
 * Non-negotiables §logging: BEFORE + AFTER + ERROR on mutation lifecycle.
 */

import { useRef, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { LanguageCode, UserProfile, UserError } from "../domain/types";
import { userRepository } from "../data/userRepository";
import { ME_QUERY_KEY } from "./useMe";
import { logVerbose, logWarn, logError } from "../data/logger";

// ---------------------------------------------------------------------------
// Hook return type
// ---------------------------------------------------------------------------

export interface UseUpdateLanguageResult {
  /**
   * Trigger the language update mutation.
   * @param language - Target language code: 'es', 'en', or 'fr'.
   */
  mutate: (language: LanguageCode) => void;
  /** True while the PATCH request is in-flight. */
  isPending: boolean;
  /** Typed error from the last failed mutation. null if no error. */
  error: UserError | null;
  /** Reset mutation state (clear error). */
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Mutation hook for updating the user's preferred language.
 *
 * Optimistic update: language switches instantly in the UI,
 * then the PATCH confirms it server-side.
 * On error: reverts to the previous language.
 *
 * @param onAuthFailure - Called when session expires during the mutation.
 * @returns UseUpdateLanguageResult
 */
export function useUpdateLanguage(onAuthFailure: () => void): UseUpdateLanguageResult {
  const queryClient = useQueryClient();
  const { i18n } = useTranslation();

  /**
   * Tracks the last intended language to guard against mutation races.
   * If user clicks ES→EN→FR rapidly, only the FR response should be committed.
   */
  const lastIntendedLanguageRef = useRef<LanguageCode | null>(null);

  const mutation = useMutation<UserProfile, UserError, LanguageCode, { previousProfile: UserProfile | undefined; previousLanguage: string }>({
    mutationFn: async (language: LanguageCode) => {
      logVerbose("user.hook.useUpdateLanguage.mutate.start", { language });

      const result = await userRepository.updateLanguage(language, onAuthFailure);

      if (!result.ok) {
        logError("user.hook.useUpdateLanguage.mutate.error", {
          error: result.error.code,
          language,
        });
        throw result.error;
      }

      logVerbose("user.hook.useUpdateLanguage.mutate.ok", {
        user_id: result.value.id,
        preferred_language: result.value.preferred_language,
      });

      return result.value;
    },

    onMutate: async (language: LanguageCode) => {
      // Track the last intended language for the race guard.
      lastIntendedLanguageRef.current = language;

      // Cancel in-flight queries to prevent cache overwrites.
      await queryClient.cancelQueries({ queryKey: ME_QUERY_KEY });

      // Snapshot current profile for rollback.
      const previousProfile = queryClient.getQueryData<UserProfile>(ME_QUERY_KEY);
      const previousLanguage = i18n.language;

      // Optimistic update: immediately apply the new language in the UI.
      i18n.changeLanguage(language).catch(() => void 0);

      // Optimistic cache update.
      if (previousProfile !== undefined) {
        queryClient.setQueryData<UserProfile>(ME_QUERY_KEY, {
          ...previousProfile,
          preferred_language: language,
        });
      }

      logVerbose("user.hook.useUpdateLanguage.optimistic", {
        language,
        previous_language: previousLanguage,
      });

      return { previousProfile, previousLanguage };
    },

    onError: (err: UserError, language: LanguageCode, context) => {
      logWarn("user.hook.useUpdateLanguage.error.revert", {
        error: err.code,
        language,
      });

      // Revert i18n to the previous language.
      if (context?.previousLanguage !== undefined) {
        i18n.changeLanguage(context.previousLanguage).catch(() => void 0);
      }

      // Revert query cache to the previous profile.
      if (context?.previousProfile !== undefined) {
        queryClient.setQueryData<UserProfile>(ME_QUERY_KEY, context.previousProfile);
      } else {
        queryClient.removeQueries({ queryKey: ME_QUERY_KEY });
      }

      // Propagate auth failure if 401 exhausted.
      if (err.code === "USER_AUTH_EXPIRED") {
        logWarn("user.hook.useUpdateLanguage.auth_failure");
        onAuthFailure();
      }
    },

    onSuccess: (updatedProfile: UserProfile, language: LanguageCode) => {
      // Race guard: ignore stale success callbacks.
      if (lastIntendedLanguageRef.current !== language) {
        logVerbose("user.hook.useUpdateLanguage.stale_success_ignored", {
          intended: lastIntendedLanguageRef.current,
          received: language,
        });
        return;
      }

      // Commit the authoritative profile from the server.
      queryClient.setQueryData<UserProfile>(ME_QUERY_KEY, updatedProfile);

      // Ensure i18n is in sync with the server's confirmed language.
      i18n.changeLanguage(updatedProfile.preferred_language).catch(() => void 0);

      logVerbose("user.hook.useUpdateLanguage.success.committed", {
        user_id: updatedProfile.id,
        preferred_language: updatedProfile.preferred_language,
      });
    },

    onSettled: () => {
      // Always invalidate to refetch authoritative profile after mutation.
      void queryClient.invalidateQueries({ queryKey: ME_QUERY_KEY });
    },
  });

  const mutate = useCallback(
    (language: LanguageCode) => {
      mutation.mutate(language);
    },
    [mutation],
  );

  return {
    mutate,
    isPending: mutation.isPending,
    error: mutation.error ?? null,
    reset: mutation.reset,
  };
}

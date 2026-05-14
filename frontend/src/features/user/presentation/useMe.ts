/**
 * Hilo People — useMe hook.
 *
 * Slice/Phase: P03-S02-T004 — AccountPage / Phase 3.
 *
 * Responsibility: TanStack Query useQuery wrapper around UserRepository.getMe().
 *   Exposes the current user's profile for AccountPage (and any other consumer).
 *   Uses AuthProvider's user as initialData to avoid a redundant /me round-trip
 *   when the profile is already hydrated at mount.
 *
 * Query key: ["user", "me"] — matches useUpdateLanguage invalidation.
 * staleTime: 60_000ms — profile rarely changes; revalidates on window focus is off.
 * enabled: only when auth status === "authenticated".
 *
 * Decision §D-T004-USER-DOMAIN-REUSE: reads UserProfile from useAuth().user as
 *   initialData; AccountPage re-fetches explicitly via refetch() when needed.
 * Decision §R4: AuthProvider.user may diverge after language update; AccountPage
 *   reads from useMe, NOT from useAuth().user, after the first render.
 *
 * Non-negotiables §logging: BEFORE + AFTER on query lifecycle.
 * Security: NEVER log email, full_name, or token values.
 */

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../auth/presentation/AuthProvider";
import { userRepository } from "../data/userRepository";
import { logVerbose, logWarn } from "../data/logger";
import type { UserProfile, UserError } from "../domain/types";

// ---------------------------------------------------------------------------
// Query key constant
// ---------------------------------------------------------------------------

/** TanStack Query key for the current user's profile. */
export const ME_QUERY_KEY = ["user", "me"] as const;

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Fetches and caches the current authenticated user's profile.
 *
 * @returns TanStack Query result for UserProfile.
 *   .data: UserProfile | undefined
 *   .isPending: true while fetching with no cached data
 *   .isError: true if UserError was returned
 *   .error: typed UserError | null
 *   .refetch(): trigger manual refetch
 */
export function useMe() {
  const { status, user } = useAuth();

  logVerbose("user.hook.useMe.render", { auth_status: status });

  return useQuery<UserProfile, UserError>({
    queryKey: ME_QUERY_KEY,

    // Only fetch when authenticated. Avoids spurious requests during hydration.
    enabled: status === "authenticated",

    // Seed cache from AuthProvider's hydrated user — prevents redundant /me call.
    initialData: user ?? undefined,

    // Profile rarely changes between visits; stale after 60s.
    staleTime: 60_000,

    // Avoid redundant fetches on tab focus — manual refetch is preferred.
    refetchOnWindowFocus: false,

    queryFn: async () => {
      logVerbose("user.hook.useMe.queryFn.start");

      const result = await userRepository.getMe();

      if (!result.ok) {
        logWarn("user.hook.useMe.queryFn.error", { error: result.error.code });
        throw result.error;
      }

      logVerbose("user.hook.useMe.queryFn.ok", {
        user_id: result.value.id,
        preferred_language: result.value.preferred_language,
      });

      return result.value;
    },
  });
}

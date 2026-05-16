/**
 * Hilo People — Single-flight (inflight-dedupe) helper for POST /api/v1/auth/refresh.
 *
 * Slice/Phase: P03-S01-T006 — Single-flight refresh to prevent 401 under StrictMode /
 *   concurrent callers / Phase 3.
 *
 * Responsibility: Ensures that concurrent callers of AuthRepository.refresh() produce
 *   exactly ONE network POST to /api/v1/auth/refresh. Any second caller that arrives
 *   while a refresh is in-flight receives the SAME Promise and therefore the SAME Result.
 *
 * Why this file exists (§D-T006-FILESIZE-PROACTIVE):
 *   authRepository.ts is already over the 300-line hard cap. Adding the single-flight
 *   inline would push it further. Extracted to a dedicated sibling module (mirrors the
 *   existing httpClient.ts _inflight pattern which covers the 401-retry path).
 *
 * Why NOT unified with httpClient._inflight (§D-T006-EXISTING-INFLIGHT-IS-DIFFERENT):
 *   httpClient._inflight only fires when authFetch intercepts a 401 on a protected request.
 *   AuthProvider.useEffect calls repo.refresh() DIRECTLY (bootstrap path), bypassing authFetch
 *   entirely. Two separate code paths. Not combined per YAGNI.
 *
 * StrictMode double-mount context (§D-T006-INFLIGHT-PROMISE):
 *   React 18 StrictMode (active in Vite dev) mounts effects TWICE in development. Without
 *   this helper the second mount fires a second POST /auth/refresh while the first is still
 *   in-flight. The backend revokes the refresh token on first use; the second call gets a 401.
 *   The instance-scoped singleton deduplicates those concurrent calls within the same
 *   AuthRepository instance (= one bundle/tab).
 *
 * Cross-tab limitation: Each AuthRepository instance has its own RefreshInflightState
 *   object. Two separate browser tabs have independent AuthProvider/AuthRepository instances
 *   and will each fire their own refresh. Cross-tab deduplication (BroadcastChannel/
 *   SharedWorker) is explicitly OUT-OF-SCOPE (§10 of task pack).
 *
 * State design (§D-T006-MODULE-SCOPE-RISK):
 *   The inflight slot is per-AuthRepository-instance, stored as a plain object reference
 *   `{ current: Promise | null }` owned by the instance. This avoids cross-test bleed:
 *   each test typically creates a fresh AuthRepository, which starts with `{ current: null }`.
 *   Tests that share a repo instance can call _resetRefreshInflight(state) in beforeEach
 *   as an extra safety measure.
 *
 * Clean Architecture: data layer only. Presentation must NOT import this directly.
 *
 * Non-negotiables §logging: BEFORE (start) / dedupe_hit / AFTER (ok, expired, error).
 *   PII contract (§D-T006-LOGS-PII-CLEAN): never log token value, never log request_id
 *   from the inflight caller — only log the event name.
 *
 * Dependencies beyond imports: logger.ts (logVerbose).
 */

import type { Result } from "../domain/AuthRepository";
import { logVerbose } from "./logger";

// ---------------------------------------------------------------------------
// State shape — per-instance, not module-level
// ---------------------------------------------------------------------------

/**
 * Mutable container for the in-flight Promise reference.
 * Create one per AuthRepository instance: `{ current: null }`.
 * Passed by reference so refreshOnce can mutate it without closures.
 */
export interface RefreshInflightState {
  current: Promise<Result<string>> | null;
}

// ---------------------------------------------------------------------------
// refreshOnce — single-flight wrapper for the refresh fetch
// ---------------------------------------------------------------------------

/**
 * Wraps a `fetcher` function so that concurrent callers share one in-flight Promise.
 *
 * If a refresh is already in-flight (state.current !== null), returns the existing
 * Promise (dedupe_hit) and emits a log for observability.
 *
 * The in-flight slot is reset in a `finally` block so that:
 *   - On SUCCESS: the next caller starts a fresh fetch (session has been rotated).
 *   - On ERROR (401, network, parse): the slot clears too, so the next caller retries.
 *   This prevents "poisoned singleton" where a failed refresh permanently blocks future
 *   refresh attempts (§D-T006-INFLIGHT-PROMISE invariant).
 *
 * @param state   - Per-instance mutable container `{ current: Promise | null }`.
 * @param fetcher - Zero-arg factory that performs the actual POST /auth/refresh.
 * @returns Promise resolving to the same Result<string> for all concurrent callers.
 */
export async function refreshOnce(
  state: RefreshInflightState,
  fetcher: () => Promise<Result<string>>,
): Promise<Result<string>> {
  if (state.current !== null) {
    logVerbose("auth.repo.refresh.dedupe_hit");
    return state.current;
  }

  logVerbose("auth.repo.refresh.start");
  state.current = fetcher().finally(() => {
    state.current = null;
  });
  return state.current;
}

// ---------------------------------------------------------------------------
// Test utility — reset a specific state object
// ---------------------------------------------------------------------------

/**
 * Resets the inflight state object to null.
 *
 * USE IN TESTS ONLY. For typical tests where each describe/it creates a fresh
 * AuthRepository instance, no explicit reset is needed — each instance starts
 * with `{ current: null }`. Call this only when a test shares a repo instance
 * across multiple calls and needs to guarantee a clean state.
 *
 * @internal
 */
export function _resetRefreshInflight(state: RefreshInflightState): void {
  state.current = null;
}

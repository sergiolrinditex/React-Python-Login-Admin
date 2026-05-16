/**
 * Hilo People — Unit tests for refreshSingleFlight.ts.
 *
 * Slice/Phase: P03-S01-T006 — Single-flight refresh to prevent 401 under StrictMode /
 *   concurrent callers / Phase 3.
 *
 * Responsibility: Verifies the refreshOnce() single-flight wrapper:
 *   - Single caller → 1 fetcher invocation, result returned correctly.
 *   - Concurrent callers share one in-flight Promise (factory called exactly once).
 *   - Sequential callers each start a fresh fetch (singleton resets in finally).
 *   - Error path resets the singleton so the next caller retries cleanly.
 *   - Massive concurrency (20 callers) — still exactly 1 factory invocation.
 *   - dedupe_hit log fires for deduped callers.
 *   - _resetRefreshInflight() clears the state object.
 *
 * Test policy (§D-T006-TEST-DIR-COLOCATE, non-negotiables §tests):
 *   - No network calls; fetcher is a vi.fn() returning a controlled Promise.
 *   - State object { current: null } created fresh per test (per-instance design).
 *   - No global reset needed — each test uses its own state object (§D-T006-MODULE-SCOPE-RISK).
 *
 * Test IDs mapped to task pack §8.1 (RSF-T01 through RSF-T09).
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { refreshOnce, _resetRefreshInflight, type RefreshInflightState } from "../refreshSingleFlight";
import type { Result } from "../../domain/AuthRepository";
import { AuthSessionExpiredError } from "../errors";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const OK_RESULT: Result<string> = { ok: true, value: "access-token-abc" };
const ERR_RESULT: Result<string> = { ok: false, error: new AuthSessionExpiredError() };

/** Creates a fresh per-test state object (clean slate, no cross-test bleed). */
function makeState(): RefreshInflightState {
  return { current: null };
}

function makeResolvedFetcher(result: Result<string> = OK_RESULT) {
  return vi.fn(() => Promise.resolve(result));
}

function makePendingFetcher(): {
  fetcher: () => Promise<Result<string>>;
  resolve: (r: Result<string>) => void;
  reject: (e: Error) => void;
} {
  let resolve!: (r: Result<string>) => void;
  let reject!: (e: Error) => void;
  const promise = new Promise<Result<string>>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  const fetcher = vi.fn().mockReturnValue(promise);
  return { fetcher, resolve, reject };
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// RSF-T01 — Single caller → fetcher invoked once, result returned
// ---------------------------------------------------------------------------

describe("RSF-T01 — single caller: fetcher invoked once, result returned", () => {
  it("calls fetcher exactly once and returns its result", async () => {
    const state = makeState();
    const fetcher = makeResolvedFetcher(OK_RESULT);

    const result = await refreshOnce(state, fetcher);

    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(result).toEqual(OK_RESULT);
  });
});

// ---------------------------------------------------------------------------
// RSF-T02 — 2 concurrent callers → 1 fetcher invocation, both receive same result
// ---------------------------------------------------------------------------

describe("RSF-T02 — 2 concurrent callers share one in-flight Promise", () => {
  it("fetcher called once; both callers receive the same Result", async () => {
    const state = makeState();
    const { fetcher, resolve } = makePendingFetcher();

    const p1 = refreshOnce(state, fetcher);
    const p2 = refreshOnce(state, fetcher);

    resolve(OK_RESULT);

    const [r1, r2] = await Promise.all([p1, p2]);

    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(r1).toEqual(OK_RESULT);
    expect(r2).toEqual(OK_RESULT);
    // Both callers receive literally the same Result object
    expect(r1).toBe(r2);
  });
});

// ---------------------------------------------------------------------------
// RSF-T03 — 5 concurrent callers → 1 fetcher invocation
// ---------------------------------------------------------------------------

describe("RSF-T03 — 5 concurrent callers all share one in-flight", () => {
  it("fetcher called once; all 5 callers receive the same Result", async () => {
    const state = makeState();
    const { fetcher, resolve } = makePendingFetcher();

    const promises = Array.from({ length: 5 }, () => refreshOnce(state, fetcher));
    resolve(OK_RESULT);

    const results = await Promise.all(promises);

    expect(fetcher).toHaveBeenCalledTimes(1);
    for (const r of results) {
      expect(r).toEqual(OK_RESULT);
    }
  });
});

// ---------------------------------------------------------------------------
// RSF-T04 — Sequential callers (A completes then B calls) → 2 fetcher invocations
// ---------------------------------------------------------------------------

describe("RSF-T04 — sequential callers: inflight resets in finally, next caller retries", () => {
  it("second call after first resolves triggers a new fetcher invocation", async () => {
    const state = makeState();
    const fetcher = makeResolvedFetcher(OK_RESULT);

    const r1 = await refreshOnce(state, fetcher);
    // inflight is now null (finally block ran)
    const r2 = await refreshOnce(state, fetcher);

    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(r1).toEqual(OK_RESULT);
    expect(r2).toEqual(OK_RESULT);
  });
});

// ---------------------------------------------------------------------------
// RSF-T05 — Fetcher rejects (network error) → singleton resets, next caller retries
// ---------------------------------------------------------------------------

describe("RSF-T05 — fetcher rejects: inflight resets so next caller starts fresh", () => {
  it("Promise rejection clears inflight; subsequent call invokes fetcher again", async () => {
    const state = makeState();
    const networkError = new Error("Network failure");
    const rejectingFetcher = vi.fn(() => Promise.reject(networkError) as Promise<Result<string>>);
    const successFetcher = makeResolvedFetcher(OK_RESULT);

    // First call — fetcher rejects
    await expect(refreshOnce(state, rejectingFetcher)).rejects.toThrow("Network failure");

    // After rejection, inflight must be null — use a fresh fetcher for the next call
    const r2 = await refreshOnce(state, successFetcher);

    expect(successFetcher).toHaveBeenCalledTimes(1);
    expect(r2).toEqual(OK_RESULT);
  });
});

// ---------------------------------------------------------------------------
// RSF-T06 — Fetcher returns {ok:false}: 2 concurrent callers both receive same err Result
// ---------------------------------------------------------------------------

describe("RSF-T06 — fetcher returns ok:false; concurrent callers both receive error Result", () => {
  it("both callers get the same AuthSessionExpiredError result; fetcher called once", async () => {
    const state = makeState();
    const { fetcher, resolve } = makePendingFetcher();

    const p1 = refreshOnce(state, fetcher);
    const p2 = refreshOnce(state, fetcher);

    resolve(ERR_RESULT);

    const [r1, r2] = await Promise.all([p1, p2]);

    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(r1.ok).toBe(false);
    expect(r2.ok).toBe(false);
    expect(r1).toBe(r2);
  });
});

// ---------------------------------------------------------------------------
// RSF-T07 — _resetRefreshInflight() clears state; next caller starts fresh
// ---------------------------------------------------------------------------

describe("RSF-T07 — _resetRefreshInflight clears inflight regardless of pending state", () => {
  it("after manual reset, next call starts a new fetcher invocation", async () => {
    const state = makeState();
    const { fetcher: f1 } = makePendingFetcher();
    const f2 = makeResolvedFetcher(OK_RESULT);

    // Start an inflight but do NOT await it
    const _p1 = refreshOnce(state, f1); // eslint-disable-line @typescript-eslint/no-floating-promises

    // Manual reset simulates test teardown or emergency clear
    _resetRefreshInflight(state);

    // Next caller should start fresh (state.current was replaced by null)
    const r2 = await refreshOnce(state, f2);

    expect(f2).toHaveBeenCalledTimes(1);
    expect(r2).toEqual(OK_RESULT);
    // _p1 is left unresolved — not awaited; acceptable in unit test cleanup context
  });
});

// ---------------------------------------------------------------------------
// RSF-T08 — dedupe_hit log emitted for deduped caller
// ---------------------------------------------------------------------------

describe("RSF-T08 — dedupe_hit log emitted for 2nd caller", () => {
  it("logVerbose called with 'auth.repo.refresh.dedupe_hit' for the deduped caller", async () => {
    // Spy on console.info — logVerbose in verbose mode uses console.info.
    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => void 0);
    vi.stubEnv("VITE_ENABLE_VERBOSE_LOGGING", "true");

    const state = makeState();
    const { fetcher, resolve } = makePendingFetcher();

    const p1 = refreshOnce(state, fetcher);
    const p2 = refreshOnce(state, fetcher);

    resolve(OK_RESULT);
    await Promise.all([p1, p2]);

    // At least one console.info call must contain the dedupe_hit event name
    const allArgs = infoSpy.mock.calls.flat(Infinity);
    const hasDedupe = allArgs.some(
      (arg) => typeof arg === "string" && arg.includes("auth.repo.refresh.dedupe_hit"),
    );
    expect(hasDedupe).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// RSF-T09 (bonus) — 20 concurrent callers → exactly 1 fetcher invocation
// ---------------------------------------------------------------------------

describe("RSF-T09 — massive concurrency: 20 callers → exactly 1 factory call", () => {
  it("fetcher invoked once; all 20 callers receive the same result", async () => {
    const state = makeState();
    const { fetcher, resolve } = makePendingFetcher();

    const promises = Array.from({ length: 20 }, () => refreshOnce(state, fetcher));
    resolve(OK_RESULT);

    const results = await Promise.all(promises);

    expect(fetcher).toHaveBeenCalledTimes(1);
    for (const r of results) {
      expect(r).toEqual(OK_RESULT);
    }
  });
});

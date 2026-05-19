/**
 * Hilo People — Unit tests for refreshSingleFlight.ts single-flight module.
 *
 * Slice/Phase: P05-S01-T007 — auth store: deduplicate concurrent refresh token calls
 *   on reload to prevent race-condition logout / Phase 5.
 *
 * Responsibility: Verifies the single-flight contract of refreshAccessToken():
 *   SF-T1  — two concurrent callers → executor invoked ONCE; both resolve same token.
 *   SF-T2  — after first resolves, _inflight=null; next caller creates a NEW Promise.
 *   SF-T3  — executor rejects → both callers receive same rejection; _inflight cleaned;
 *            onAuthFailure called exactly once; AuthSessionExpiredError is the error type.
 *   SF-T4  — 5 parallel callers → executor invoked exactly once.
 *   SF-T5  — logging: verbose=true fires .start (1), .joined (N-1), .ok (1);
 *            verbose=false fires only .warn/error-level entries.
 *   SF-T6  — cross-layer F5 simulation: refreshAccessToken from "hydrate" and from
 *            "interceptor" concurrently → exactly ONE fetch to /api/v1/auth/refresh.
 *
 * Test policy (non-negotiables §tests):
 *   - fetch is mocked at the network boundary ONLY (vi.spyOn(global, 'fetch')).
 *   - No mocking of business logic from other modules.
 *   - _resetSingleFlight() is called in beforeEach to isolate in-flight state.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { refreshAccessToken, _resetSingleFlight } from "../refreshSingleFlight";
import { getAccessToken, clearAccessToken } from "../accessTokenStore";
import { AuthSessionExpiredError } from "../errors";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Returns a mock fetch that resolves with a 200 access_token response. */
function mockRefreshSuccess(token: string) {
  return vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({ data: { access_token: token, token_type: "Bearer", expires_in: 1800 } }),
      { status: 200 },
    ),
  );
}

/** Returns a mock fetch that resolves with a 401 response. */
function mockRefreshFailure(status = 401) {
  return vi.spyOn(global, "fetch").mockResolvedValue(
    new Response("{}", { status }),
  );
}

// ---------------------------------------------------------------------------
// Common setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  clearAccessToken();
  _resetSingleFlight();
});

afterEach(() => {
  clearAccessToken();
  _resetSingleFlight();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// SF-T1 — Two concurrent callers → executor invoked once; both resolve same value
// ---------------------------------------------------------------------------

describe("SF-T1 — two concurrent callers → exactly ONE fetch, both resolve with same token", () => {
  it("resolves both callers to the same token and calls fetch once", async () => {
    const fetchSpy = mockRefreshSuccess("token-sf-t1");

    const onFail1 = vi.fn();
    const onFail2 = vi.fn();

    const [t1, t2] = await Promise.all([
      refreshAccessToken({ onAuthFailure: onFail1, reason: "hydrate" }),
      refreshAccessToken({ onAuthFailure: onFail2, reason: "interceptor" }),
    ]);

    expect(t1).toBe("token-sf-t1");
    expect(t2).toBe("token-sf-t1");

    const refreshCalls = fetchSpy.mock.calls.filter((c) =>
      String(c[0]).endsWith("/api/v1/auth/refresh"),
    );
    expect(refreshCalls.length).toBe(1);

    expect(onFail1).not.toHaveBeenCalled();
    expect(onFail2).not.toHaveBeenCalled();

    // Token persisted in store
    expect(getAccessToken()).toBe("token-sf-t1");
  });
});

// ---------------------------------------------------------------------------
// SF-T2 — After first resolves, _inflight=null; next caller creates NEW promise
// ---------------------------------------------------------------------------

describe("SF-T2 — after first call resolves, next caller creates a NEW request", () => {
  it("fires a second fetch for a caller that arrives after _inflight is cleared", async () => {
    let callCount = 0;
    vi.spyOn(global, "fetch").mockImplementation(() => {
      callCount++;
      const token = callCount === 1 ? "token-first" : "token-second";
      return Promise.resolve(
        new Response(
          JSON.stringify({ data: { access_token: token, token_type: "Bearer", expires_in: 1800 } }),
          { status: 200 },
        ),
      );
    });

    const token1 = await refreshAccessToken({ reason: "hydrate" });
    expect(token1).toBe("token-first");
    expect(callCount).toBe(1);

    // After the first settles, _inflight must be null (handled by finally).
    // A second call must create a new Promise and fire another fetch.
    const token2 = await refreshAccessToken({ reason: "interceptor" });
    expect(token2).toBe("token-second");
    expect(callCount).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// SF-T3 — Executor rejects → both callers receive same rejection; onAuthFailure x1
// ---------------------------------------------------------------------------

describe("SF-T3 — executor fails → both callers reject; onAuthFailure called exactly once", () => {
  it("propagates AuthSessionExpiredError to both callers; onAuthFailure fires once", async () => {
    mockRefreshFailure(401);

    const onFail = vi.fn();

    const [r1, r2] = await Promise.allSettled([
      refreshAccessToken({ onAuthFailure: onFail, reason: "hydrate" }),
      refreshAccessToken({ onAuthFailure: onFail, reason: "interceptor" }),
    ]);

    expect(r1.status).toBe("rejected");
    expect(r2.status).toBe("rejected");

    if (r1.status === "rejected") {
      expect(r1.reason).toBeInstanceOf(AuthSessionExpiredError);
    }
    if (r2.status === "rejected") {
      expect(r2.reason).toBeInstanceOf(AuthSessionExpiredError);
    }

    // onAuthFailure is called by refreshSingleFlight exactly once per burst.
    // Both callers passed the same onFail function — it should be called once.
    expect(onFail).toHaveBeenCalledTimes(1);

    // _inflight must be cleared after failure
    expect(getAccessToken()).toBeNull();

    // A subsequent call must work again (proves _inflight was reset)
    mockRefreshSuccess("token-after-fail");
    const t = await refreshAccessToken({ reason: "manual" });
    expect(t).toBe("token-after-fail");
  });
});

// ---------------------------------------------------------------------------
// SF-T4 — 5 parallel callers → executor invoked exactly once
// ---------------------------------------------------------------------------

describe("SF-T4 — 5 parallel callers → fetch called exactly once", () => {
  it("stress: 5 concurrent callers share ONE fetch call", async () => {
    const fetchSpy = mockRefreshSuccess("token-stress");

    const results = await Promise.all(
      Array.from({ length: 5 }, (_, i) =>
        refreshAccessToken({ reason: i === 0 ? "hydrate" : "interceptor" }),
      ),
    );

    // All 5 must resolve with the same token
    results.forEach((t) => expect(t).toBe("token-stress"));

    const refreshCalls = fetchSpy.mock.calls.filter((c) =>
      String(c[0]).endsWith("/api/v1/auth/refresh"),
    );
    expect(refreshCalls.length).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// SF-T5 — Logging contract: .start x1, .joined x(N-1), .ok x1 in verbose mode
// ---------------------------------------------------------------------------

describe("SF-T5 — logging contract for concurrent callers", () => {
  it("verbose=true: fires .start once, .joined N-1 times, .ok once", async () => {
    vi.stubEnv("VITE_ENABLE_VERBOSE_LOGGING", "true");
    mockRefreshSuccess("token-log");

    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => void 0);

    await Promise.all([
      refreshAccessToken({ reason: "hydrate" }),
      refreshAccessToken({ reason: "interceptor" }),
      refreshAccessToken({ reason: "manual" }),
    ]);

    const keys = infoSpy.mock.calls.map((c) => String(c[0]));

    const startCount = keys.filter((k) => k.includes("auth.refresh.singleflight.start")).length;
    const joinedCount = keys.filter((k) => k.includes("auth.refresh.singleflight.joined")).length;
    const okCount = keys.filter((k) => k.includes("auth.refresh.singleflight.ok")).length;

    expect(startCount).toBe(1);
    // The other 2 concurrent callers joined
    expect(joinedCount).toBe(2);
    expect(okCount).toBe(1);

    vi.unstubAllEnvs();
  });

  it("verbose=false: info logs suppressed; warn/error only when failure occurs", async () => {
    vi.stubEnv("VITE_ENABLE_VERBOSE_LOGGING", "false");
    mockRefreshSuccess("token-silent");

    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => void 0);

    await Promise.all([
      refreshAccessToken({ reason: "hydrate" }),
      refreshAccessToken({ reason: "interceptor" }),
    ]);

    // No info log should fire for the single-flight module in quiet mode
    const sfInfos = infoSpy.mock.calls
      .map((c) => String(c[0]))
      .filter((k) => k.includes("singleflight"));
    expect(sfInfos.length).toBe(0);

    vi.unstubAllEnvs();
  });
});

// ---------------------------------------------------------------------------
// SF-T6 — Cross-layer F5 simulation (AC3): hydrate + interceptor path
// ---------------------------------------------------------------------------

describe("SF-T6 — cross-layer: hydrate + interceptor fire concurrently → 1 fetch", () => {
  it("simulates F5: AuthProvider.hydrate() (reason=hydrate) and 401 interceptor " +
    "(reason=interceptor) share ONE /api/v1/auth/refresh call", async () => {
    const fetchSpy = mockRefreshSuccess("token-f5");

    const onFail = vi.fn();

    const [hydrateToken, interceptorToken] = await Promise.all([
      // AuthProvider.hydrate() path — calls repo.refresh() → refreshAccessToken(hydrate)
      refreshAccessToken({ onAuthFailure: onFail, reason: "hydrate" }),
      // httpClient._doRefresh() path — calls refreshAccessToken(interceptor)
      refreshAccessToken({ onAuthFailure: onFail, reason: "interceptor" }),
    ]);

    // Both paths must see the same new token
    expect(hydrateToken).toBe("token-f5");
    expect(interceptorToken).toBe("token-f5");

    // The fetch to /api/v1/auth/refresh must have been called exactly once
    const refreshCalls = fetchSpy.mock.calls.filter((c) =>
      String(c[0]).endsWith("/api/v1/auth/refresh"),
    );
    expect(refreshCalls.length).toBe(1);

    // Token is persisted in the access token store
    expect(getAccessToken()).toBe("token-f5");

    // onAuthFailure must NOT have been called (happy path)
    expect(onFail).not.toHaveBeenCalled();
  });

  it("F5 failure: both hydrate and interceptor receive AuthSessionExpiredError", async () => {
    mockRefreshFailure(401);

    const onFail = vi.fn();

    const [r1, r2] = await Promise.allSettled([
      refreshAccessToken({ onAuthFailure: onFail, reason: "hydrate" }),
      refreshAccessToken({ onAuthFailure: onFail, reason: "interceptor" }),
    ]);

    expect(r1.status).toBe("rejected");
    expect(r2.status).toBe("rejected");

    if (r1.status === "rejected") {
      expect(r1.reason).toBeInstanceOf(AuthSessionExpiredError);
    }

    // clearAccessToken() was called exactly once (inside the module), and
    // onAuthFailure was called exactly once — not twice.
    expect(onFail).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
  });
});

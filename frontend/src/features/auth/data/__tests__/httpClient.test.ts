/**
 * Hilo People — Unit tests for httpClient.ts API_BASE same-origin contract.
 *
 * Slice/Phase: P03-S01-T007 — httpClient.ts API_BASE fallback fix / Phase 3.
 *
 * Responsibility: Verifies that when VITE_API_BASE_URL is unset/empty:
 *   - authFetch passes relative paths to global.fetch as-is (ADR-002 same-origin).
 *   - Absolute URLs are preserved unchanged (legacy / future explicit-base case).
 *   - The single-flight refresh flow uses the relative REFRESH_URL ("/api/v1/auth/refresh").
 *
 * Motivation: §D-T007-COVERAGE-NEW-TESTFILE (WRITE_SET_DRIFT, pre-authorized).
 *   auth.test.tsx is already 974 lines; adding these assertions there would push it
 *   significantly beyond the 300-line cap for a single file. This new file isolates
 *   the URL-formation contract in a dedicated, maintainable unit.
 *
 * ADR-002 reference: VITE_API_BASE_URL="" → API_BASE="" → all authFetch paths are
 *   relative (e.g. "/api/v1/users/me"). Setting VITE_API_BASE_URL="http://localhost:8000"
 *   re-introduces CORS preflights and must NOT be used.
 *
 * Dependencies: authFetch, _resetInflight from httpClient.ts;
 *   setAccessToken, clearAccessToken from accessTokenStore.ts.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { authFetch, _resetInflight } from "../httpClient";
import { setAccessToken, clearAccessToken } from "../accessTokenStore";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetchCalls(
  responses: Array<{ status: number; body?: unknown }>,
) {
  let callIndex = 0;
  return vi.spyOn(global, "fetch").mockImplementation(() => {
    const resp = responses[callIndex] ?? responses[responses.length - 1];
    callIndex++;
    const bodyStr = resp.body !== undefined ? JSON.stringify(resp.body) : "";
    return Promise.resolve(
      new Response(bodyStr, {
        status: resp.status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });
}

// ---------------------------------------------------------------------------
// HC-T01 — API_BASE="": relative path passes to fetch unchanged
// ---------------------------------------------------------------------------

describe("HC-T01 — API_BASE empty: authFetch uses relative path as-is", () => {
  beforeEach(() => {
    clearAccessToken();
    _resetInflight();
  });
  afterEach(() => {
    clearAccessToken();
    _resetInflight();
    vi.restoreAllMocks();
  });

  it("authFetch('/api/v1/users/me') passes relative path to global.fetch", async () => {
    const fetchSpy = mockFetchCalls([
      { status: 200, body: { data: { id: "user-1" } } },
    ]);

    await authFetch("/api/v1/users/me");

    // The first argument to fetch MUST be the relative path — NOT an absolute URL.
    const firstArg = String(fetchSpy.mock.calls[0][0]);
    expect(firstArg).toBe("/api/v1/users/me");
    expect(firstArg.startsWith("http")).toBe(false);
  });

  it("authFetch('/api/v1/chat/conversations') keeps relative path", async () => {
    const fetchSpy = mockFetchCalls([
      { status: 200, body: { data: [] } },
    ]);

    await authFetch("/api/v1/chat/conversations");

    const firstArg = String(fetchSpy.mock.calls[0][0]);
    expect(firstArg).toBe("/api/v1/chat/conversations");
    expect(firstArg.startsWith("http")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// HC-T02 — Absolute URL passed explicitly: preserved, no double-prefix
// ---------------------------------------------------------------------------

describe("HC-T02 — Absolute URL passed to authFetch: preserved unchanged", () => {
  beforeEach(() => {
    clearAccessToken();
    _resetInflight();
  });
  afterEach(() => {
    clearAccessToken();
    _resetInflight();
    vi.restoreAllMocks();
  });

  it("authFetch('http://example.test/x') is NOT prefixed with API_BASE", async () => {
    const fetchSpy = mockFetchCalls([{ status: 200, body: {} }]);

    await authFetch("http://example.test/x");

    const firstArg = String(fetchSpy.mock.calls[0][0]);
    expect(firstArg).toBe("http://example.test/x");
  });
});

// ---------------------------------------------------------------------------
// HC-T03 — 401 → refresh single-flight: REFRESH_URL is relative
// ---------------------------------------------------------------------------

describe("HC-T03 — 401 → refresh uses relative REFRESH_URL", () => {
  beforeEach(() => {
    clearAccessToken();
    _resetInflight();
    setAccessToken("old-token");
  });
  afterEach(() => {
    clearAccessToken();
    _resetInflight();
    vi.restoreAllMocks();
  });

  it("refresh request uses relative path /api/v1/auth/refresh (not absolute)", async () => {
    // Mock a deterministic randomUUID so we can identify the refresh call by URL only.
    vi.stubGlobal(
      "crypto",
      Object.assign({}, globalThis.crypto, {
        randomUUID: vi.fn(() => "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
      }),
    );

    const fetchSpy = vi
      .spyOn(global, "fetch")
      .mockImplementationOnce(() =>
        // original request → 401
        Promise.resolve(new Response("{}", { status: 401 })),
      )
      .mockImplementationOnce(() =>
        // /auth/refresh → 200
        Promise.resolve(
          new Response(
            JSON.stringify({
              data: { access_token: "new-token", token_type: "Bearer", expires_in: 1800 },
            }),
            { status: 200 },
          ),
        ),
      )
      .mockImplementationOnce(() =>
        // retry original → 200
        Promise.resolve(new Response(JSON.stringify({ data: {} }), { status: 200 })),
      );

    const onFail = vi.fn();
    await authFetch("/api/v1/users/me", {}, { onAuthFailure: onFail });

    // The second fetch call is the refresh request.
    expect(fetchSpy).toHaveBeenCalledTimes(3);
    const refreshCallArg = String(fetchSpy.mock.calls[1][0]);
    expect(refreshCallArg).toBe("/api/v1/auth/refresh");
    expect(refreshCallArg.startsWith("http")).toBe(false);
    expect(onFail).not.toHaveBeenCalled();
  });
});

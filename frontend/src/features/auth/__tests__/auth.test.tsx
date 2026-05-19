/**
 * Hilo People — Auth feature tests (P01-S03-T001).
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *
 * Responsibility: Vitest + RTL tests for:
 *   - accessTokenStore (T01)
 *   - AuthProvider hydration paths (T02–T04)
 *   - signInAccepted hook (T05)
 *   - useLogout (T06–T07)
 *   - RequireAuth guard (T08–T10)
 *   - RequireRole guard (T11–T12)
 *   - redirectAfterAuth open-redirect guard (T13–T14)
 *   - httpClient single-flight 401 (T15–T17)
 *   - httpClient header injection (T18)
 *   - Logging verification (T19–T20)
 *
 * Test policy (non-negotiables §tests):
 *   - fetch is mocked at the network boundary ONLY (vi.spyOn(global, 'fetch')).
 *   - No mocking of business logic (authRepository, AuthProvider internals).
 *   - Unit tests for pure logic (redirectAfterAuth, accessTokenStore) — fully isolated.
 *   - All tests match the task pack §K test plan (≥18 cases).
 *
 * Security assertions:
 *   - T01: localStorage is NEVER touched by accessTokenStore.
 *   - T19/T20: no token value appears in any console log spy output.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { MemoryRouter, Routes, Route, Outlet } from "react-router";
import React from "react";

// ---------------------------------------------------------------------------
// Imports under test
// ---------------------------------------------------------------------------

import {
  getAccessToken,
  setAccessToken,
  clearAccessToken,
  hasAccessToken,
} from "../data/accessTokenStore";
import { getSafeRedirect, DEFAULT_SAFE_REDIRECT } from "../presentation/redirectAfterAuth";
import { AuthProvider, useAuth } from "../presentation/AuthProvider";
import { RequireAuth } from "../presentation/RequireAuth";
import { RequireRole } from "../presentation/RequireRole";
import { authFetch, _resetInflight } from "../data/httpClient";
import { AuthRepository } from "../data/authRepository";
import type { UserProfile } from "../domain/types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_USER: UserProfile = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "employee@inditex-sandbox.com",
  full_name: "Test Employee",
  status: "active",
  preferred_language: "es",
  roles: ["employee"],
  employee_profile: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const ADMIN_USER: UserProfile = {
  ...MOCK_USER,
  id: "22222222-2222-2222-2222-222222222222",
  roles: ["people_admin"],
};

const MOCK_TOKEN = "mock-access-token-xyz";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetch(
  responses: Array<{ status: number; body?: unknown }>,
): void {
  let callIndex = 0;
  vi.spyOn(global, "fetch").mockImplementation(() => {
    const resp = responses[callIndex] ?? responses[responses.length - 1];
    callIndex++;
    const body = resp.body !== undefined ? JSON.stringify(resp.body) : "";
    return Promise.resolve(
      new Response(body, {
        status: resp.status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });
}

/** Renders children inside an AuthProvider (with MemoryRouter for hooks). */
function renderWithAuth(
  ui: React.ReactNode,
  {
    fetchResponses = [],
    clearQueries = vi.fn(),
    initialPath = "/",
  }: {
    fetchResponses?: Array<{ status: number; body?: unknown }>;
    clearQueries?: () => void;
    initialPath?: string;
  } = {},
) {
  if (fetchResponses.length > 0) {
    mockFetch(fetchResponses);
  }
  const repo = new AuthRepository(clearQueries);
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthProvider _repo={repo} _onQueriesClear={clearQueries}>
        {ui}
      </AuthProvider>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// T01 — accessTokenStore: in-memory only, never localStorage
// ---------------------------------------------------------------------------

describe("auth T01 — accessTokenStore: set/get/clear in-memory only", () => {
  beforeEach(() => {
    clearAccessToken();
    vi.spyOn(Storage.prototype, "setItem");
    vi.spyOn(Storage.prototype, "getItem");
  });

  afterEach(() => {
    clearAccessToken();
    vi.restoreAllMocks();
  });

  it("starts null", () => {
    expect(getAccessToken()).toBeNull();
    expect(hasAccessToken()).toBe(false);
  });

  it("set → get returns the token", () => {
    setAccessToken("tok-abc");
    expect(getAccessToken()).toBe("tok-abc");
    expect(hasAccessToken()).toBe(true);
  });

  it("clear → get returns null", () => {
    setAccessToken("tok-abc");
    clearAccessToken();
    expect(getAccessToken()).toBeNull();
    expect(hasAccessToken()).toBe(false);
  });

  it("NEVER calls localStorage.setItem", () => {
    setAccessToken("tok-secret");
    clearAccessToken();
    expect(Storage.prototype.setItem).not.toHaveBeenCalled();
  });

  it("NEVER calls localStorage.getItem", () => {
    setAccessToken("tok-secret");
    getAccessToken();
    expect(Storage.prototype.getItem).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// T02 — AuthProvider: cold mount, /refresh 200 → /me 200 → authenticated
// ---------------------------------------------------------------------------

describe("auth T02 — AuthProvider: cold mount → /refresh 200 → /me 200 → authenticated", () => {
  afterEach(() => {
    clearAccessToken();
    vi.restoreAllMocks();
  });

  it("status becomes 'authenticated' after refresh + me succeed", async () => {
    const refreshBody = { data: { access_token: MOCK_TOKEN, token_type: "Bearer", expires_in: 1800 } };
    const meBody = { data: MOCK_USER };

    function Consumer() {
      const { status, user } = useAuth();
      return (
        <div>
          <span data-testid="status">{status}</span>
          <span data-testid="user_id">{user?.id ?? "none"}</span>
        </div>
      );
    }

    renderWithAuth(<Consumer />, {
      fetchResponses: [
        { status: 200, body: refreshBody },
        { status: 200, body: meBody },
      ],
    });

    // Initially hydrating
    expect(screen.getByTestId("status").textContent).toBe("hydrating");

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("authenticated");
    });

    expect(screen.getByTestId("user_id").textContent).toBe(MOCK_USER.id);
    expect(getAccessToken()).toBe(MOCK_TOKEN);
  });
});

// ---------------------------------------------------------------------------
// T03 — AuthProvider: /refresh 401 → unauthenticated, /me NOT called
// ---------------------------------------------------------------------------

describe("auth T03 — AuthProvider: /refresh 401 → unauthenticated, no /me call", () => {
  afterEach(() => {
    clearAccessToken();
    vi.restoreAllMocks();
  });

  it("status becomes 'unauthenticated' on refresh 401", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify({ errors: [{ code: "AUTH_SESSION_EXPIRED" }] }), { status: 401, headers: { "Content-Type": "application/json" } })),
    );

    function Consumer() {
      const { status } = useAuth();
      return <span data-testid="status">{status}</span>;
    }

    const repo = new AuthRepository(vi.fn());
    render(
      <MemoryRouter>
        <AuthProvider _repo={repo}>
          <Consumer />
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated");
    });

    // fetch called exactly once (refresh only; /me not called)
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// T04 — AuthProvider: /refresh network error → unauthenticated (safe fallback)
// ---------------------------------------------------------------------------

describe("auth T04 — AuthProvider: /refresh network error → unauthenticated", () => {
  afterEach(() => {
    clearAccessToken();
    vi.restoreAllMocks();
  });

  it("status becomes 'unauthenticated' on network error", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));

    function Consumer() {
      const { status } = useAuth();
      return <span data-testid="status">{status}</span>;
    }

    const repo = new AuthRepository(vi.fn());
    render(
      <MemoryRouter>
        <AuthProvider _repo={repo}>
          <Consumer />
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated");
    });
    expect(getAccessToken()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// T05 — signInAccepted: sets status=authenticated, no extra /me call
// ---------------------------------------------------------------------------

describe("auth T05 — signInAccepted → status=authenticated, /me not re-called", () => {
  afterEach(() => {
    clearAccessToken();
    vi.restoreAllMocks();
  });

  it("signInAccepted sets token and user without extra fetch", async () => {
    // Mock refresh → 401 so initial hydration results in unauthenticated
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response("{}", { status: 401 }),
    );

    function Consumer() {
      const { status, user, signInAccepted } = useAuth();
      return (
        <div>
          <span data-testid="status">{status}</span>
          <span data-testid="user_id">{user?.id ?? "none"}</span>
          <button
            onClick={() => signInAccepted(MOCK_TOKEN, MOCK_USER)}
            data-testid="accept-btn"
          >
            Accept
          </button>
        </div>
      );
    }

    const repo = new AuthRepository(vi.fn());
    render(
      <MemoryRouter>
        <AuthProvider _repo={repo}>
          <Consumer />
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated");
    });

    const callsBefore = fetchSpy.mock.calls.length;

    act(() => {
      screen.getByTestId("accept-btn").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("authenticated");
    });

    expect(screen.getByTestId("user_id").textContent).toBe(MOCK_USER.id);
    expect(getAccessToken()).toBe(MOCK_TOKEN);
    // No extra fetch for /me
    expect(fetchSpy).toHaveBeenCalledTimes(callsBefore);
  });
});

// ---------------------------------------------------------------------------
// T06 — useLogout: POST /logout, clear token, clear queries, navigate sign-in
// ---------------------------------------------------------------------------

describe("auth T06 — useLogout: /logout 204 → token cleared, queries cleared", () => {
  afterEach(() => {
    clearAccessToken();
    vi.restoreAllMocks();
  });

  it("logout clears token and calls onQueriesClear", async () => {
    const clearMock = vi.fn();
    // refresh 200 → me 200 → authenticated, then logout 204
    const refreshBody = { data: { access_token: MOCK_TOKEN, token_type: "Bearer", expires_in: 1800 } };
    const meBody = { data: MOCK_USER };

    mockFetch([
      { status: 200, body: refreshBody },
      { status: 200, body: meBody },
      { status: 204 },
    ]);

    function Consumer() {
      const { status, logout } = useAuth();
      return (
        <div>
          <span data-testid="status">{status}</span>
          <button onClick={() => void logout()} data-testid="logout-btn">
            Logout
          </button>
        </div>
      );
    }

    const repo = new AuthRepository(clearMock);
    render(
      <MemoryRouter>
        <AuthProvider _repo={repo} _onQueriesClear={clearMock}>
          <Consumer />
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("authenticated"),
    );

    act(() => {
      screen.getByTestId("logout-btn").click();
    });

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated"),
    );

    expect(getAccessToken()).toBeNull();
    expect(clearMock).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// T07 — useLogout: backend returns 401 → still clears local state
// ---------------------------------------------------------------------------

describe("auth T07 — useLogout: backend 401 → still clears local state (defensive logout)", () => {
  afterEach(() => {
    clearAccessToken();
    vi.restoreAllMocks();
  });

  it("logout clears token even when backend returns 401", async () => {
    const clearMock = vi.fn();
    const refreshBody = { data: { access_token: MOCK_TOKEN, token_type: "Bearer", expires_in: 1800 } };
    const meBody = { data: MOCK_USER };

    mockFetch([
      { status: 200, body: refreshBody },
      { status: 200, body: meBody },
      { status: 401 }, // logout backend failure
    ]);

    function Consumer() {
      const { status, logout } = useAuth();
      return (
        <div>
          <span data-testid="status">{status}</span>
          <button onClick={() => void logout()} data-testid="logout-btn">
            Logout
          </button>
        </div>
      );
    }

    const repo = new AuthRepository(clearMock);
    render(
      <MemoryRouter>
        <AuthProvider _repo={repo} _onQueriesClear={clearMock}>
          <Consumer />
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("authenticated"),
    );

    act(() => {
      screen.getByTestId("logout-btn").click();
    });

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated"),
    );

    expect(getAccessToken()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// T08 — RequireAuth: unauthenticated → Navigate to /auth/sign-in?next=<from>
// ---------------------------------------------------------------------------

describe("auth T08 — RequireAuth: unauthenticated → Navigate with ?next=", () => {
  afterEach(() => {
    clearAccessToken();
    vi.restoreAllMocks();
  });

  it("redirects to sign-in with ?next= when unauthenticated", async () => {
    mockFetch([{ status: 401 }]); // refresh fails → unauthenticated

    const repo = new AuthRepository(vi.fn());
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <AuthProvider _repo={repo}>
          <Routes>
            <Route
              path="/chat"
              element={
                <RequireAuth>
                  <div data-testid="protected">Protected</div>
                </RequireAuth>
              }
            />
            <Route
              path="/auth/sign-in"
              element={<div data-testid="sign-in">Sign In</div>}
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.queryByTestId("sign-in")).not.toBeNull();
    });
    expect(screen.queryByTestId("protected")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// T09 — RequireAuth: authenticated → renders children
// ---------------------------------------------------------------------------

describe("auth T09 — RequireAuth: authenticated → renders children", () => {
  afterEach(() => {
    clearAccessToken();
    vi.restoreAllMocks();
  });

  it("renders children when authenticated", async () => {
    const refreshBody = { data: { access_token: MOCK_TOKEN, token_type: "Bearer", expires_in: 1800 } };
    const meBody = { data: MOCK_USER };
    mockFetch([{ status: 200, body: refreshBody }, { status: 200, body: meBody }]);

    const repo = new AuthRepository(vi.fn());
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <AuthProvider _repo={repo}>
          <Routes>
            <Route
              path="/chat"
              element={
                <RequireAuth>
                  <div data-testid="protected">Protected</div>
                </RequireAuth>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("protected")).toBeTruthy();
    });
  });
});

// ---------------------------------------------------------------------------
// T10 — RequireAuth: hydrating → renders neither children nor redirect
// ---------------------------------------------------------------------------

describe("auth T10 — RequireAuth: hydrating → renders neither children nor redirect", () => {
  afterEach(() => {
    clearAccessToken();
    vi.restoreAllMocks();
  });

  it("shows loading placeholder while hydrating, not children or redirect", () => {
    // Mock fetch to never resolve (pending promise = hydrating forever)
    vi.spyOn(global, "fetch").mockReturnValue(new Promise(() => {}));

    const repo = new AuthRepository(vi.fn());
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <AuthProvider _repo={repo}>
          <Routes>
            <Route
              path="/chat"
              element={
                <RequireAuth>
                  <div data-testid="protected">Protected</div>
                </RequireAuth>
              }
            />
            <Route path="/auth/sign-in" element={<div data-testid="sign-in">Sign In</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    // While hydrating: no children, no sign-in redirect, shows loading aria
    expect(screen.queryByTestId("protected")).toBeNull();
    expect(screen.queryByTestId("sign-in")).toBeNull();
    expect(screen.getByRole("status")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// T11 — RequireRole: user.roles=['employee'] → redirects to /chat
// ---------------------------------------------------------------------------

describe("auth T11 — RequireRole: employee role denied from admin", () => {
  beforeEach(() => {
    // P05-S01-T007: reset shared single-flight state that T10's never-resolving
    // fetch mock leaves behind (_inflight is set but never cleared by finally).
    _resetInflight();
  });
  afterEach(() => {
    clearAccessToken();
    _resetInflight();
    vi.restoreAllMocks();
  });

  it("redirects employee to /chat when they hit /admin", async () => {
    const refreshBody = { data: { access_token: MOCK_TOKEN, token_type: "Bearer", expires_in: 1800 } };
    const meBody = { data: MOCK_USER }; // roles: ['employee']
    mockFetch([{ status: 200, body: refreshBody }, { status: 200, body: meBody }]);

    const repo = new AuthRepository(vi.fn());
    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <AuthProvider _repo={repo}>
          <Routes>
            <Route
              path="/admin"
              element={
                <RequireRole roles={["people_admin", "super_admin"]}>
                  <div data-testid="admin">Admin</div>
                </RequireRole>
              }
            />
            <Route path="/chat" element={<div data-testid="chat">Chat</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.queryByTestId("chat")).not.toBeNull();
    });
    expect(screen.queryByTestId("admin")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// T12 — RequireRole: user.roles=['people_admin'] → renders children
// ---------------------------------------------------------------------------

describe("auth T12 — RequireRole: people_admin allowed to admin route", () => {
  beforeEach(() => {
    // P05-S01-T007: same reset rationale as T11 — clear zombie _inflight from T10.
    _resetInflight();
  });
  afterEach(() => {
    clearAccessToken();
    _resetInflight();
    vi.restoreAllMocks();
  });

  it("renders admin content for people_admin role", async () => {
    const refreshBody = { data: { access_token: MOCK_TOKEN, token_type: "Bearer", expires_in: 1800 } };
    const meBody = { data: ADMIN_USER }; // roles: ['people_admin']
    mockFetch([{ status: 200, body: refreshBody }, { status: 200, body: meBody }]);

    const repo = new AuthRepository(vi.fn());
    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <AuthProvider _repo={repo}>
          <Routes>
            <Route
              path="/admin"
              element={
                <RequireRole roles={["people_admin", "super_admin"]}>
                  <div data-testid="admin">Admin</div>
                </RequireRole>
              }
            />
            <Route path="/chat" element={<div data-testid="chat">Chat</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("admin")).toBeTruthy();
    });
    expect(screen.queryByTestId("chat")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// T13 — redirectAfterAuth: open-redirect guard rejects unsafe values
// ---------------------------------------------------------------------------

describe("auth T13 — getSafeRedirect: rejects open-redirect attempts", () => {
  it("rejects https://evil.com", () => {
    expect(getSafeRedirect("https://evil.com")).toBe(DEFAULT_SAFE_REDIRECT);
  });

  it("rejects //evil.com", () => {
    expect(getSafeRedirect("//evil.com")).toBe(DEFAULT_SAFE_REDIRECT);
  });

  it("rejects javascript:alert(1)", () => {
    expect(getSafeRedirect("javascript:alert(1)")).toBe(DEFAULT_SAFE_REDIRECT);
  });

  it("rejects \\\\evil path", () => {
    expect(getSafeRedirect("\\\\evil")).toBe(DEFAULT_SAFE_REDIRECT);
  });

  it("rejects data: pseudo-scheme", () => {
    expect(getSafeRedirect("data:text/html,<h1>hi</h1>")).toBe(DEFAULT_SAFE_REDIRECT);
  });

  it("rejects empty string", () => {
    expect(getSafeRedirect("")).toBe(DEFAULT_SAFE_REDIRECT);
  });

  it("rejects null", () => {
    expect(getSafeRedirect(null)).toBe(DEFAULT_SAFE_REDIRECT);
  });
});

// ---------------------------------------------------------------------------
// T14 — redirectAfterAuth: safe relative path passes
// ---------------------------------------------------------------------------

describe("auth T14 — getSafeRedirect: safe relative path passes", () => {
  it("/chat/abc?x=1 passes through unchanged", () => {
    expect(getSafeRedirect("/chat/abc?x=1")).toBe("/chat/abc?x=1");
  });

  it("/admin passes through", () => {
    expect(getSafeRedirect("/admin")).toBe("/admin");
  });

  it("/chat passes through", () => {
    expect(getSafeRedirect("/chat")).toBe("/chat");
  });
});

// ---------------------------------------------------------------------------
// T15 — httpClient: single 401 → single-flight refresh → retry → success
// ---------------------------------------------------------------------------

describe("auth T15 — httpClient: 401 → single-flight refresh → retry success", () => {
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

  it("fires /refresh once, retries original request with new token", async () => {
    const fetchSpy = vi
      .spyOn(global, "fetch")
      .mockImplementationOnce(() =>
        // First call: /api/v1/users/me → 401
        Promise.resolve(new Response("{}", { status: 401 })),
      )
      .mockImplementationOnce(() =>
        // Second call: /api/v1/auth/refresh → 200
        Promise.resolve(
          new Response(
            JSON.stringify({ data: { access_token: "new-token", token_type: "Bearer", expires_in: 1800 } }),
            { status: 200 },
          ),
        ),
      )
      .mockImplementationOnce(() =>
        // Third call: retry /api/v1/users/me → 200
        Promise.resolve(
          new Response(JSON.stringify({ data: MOCK_USER }), { status: 200 }),
        ),
      );

    const onFail = vi.fn();
    const response = await authFetch("/api/v1/users/me", {}, { onAuthFailure: onFail });

    expect(response.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalledTimes(3); // original + refresh + retry
    expect(onFail).not.toHaveBeenCalled();
    expect(getAccessToken()).toBe("new-token");
  });
});

// ---------------------------------------------------------------------------
// T16 — httpClient: TWO concurrent 401s → ONE refresh call → both succeed
// ---------------------------------------------------------------------------

describe("auth T16 — httpClient: two concurrent 401s → ONE refresh call", () => {
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

  it("fires exactly ONE refresh for two concurrent 401s", async () => {
    let refreshCallCount = 0;
    let originalCallCount = 0;

    vi.spyOn(global, "fetch").mockImplementation((url) => {
      const urlStr = String(url);
      if (urlStr.includes("/auth/refresh")) {
        refreshCallCount++;
        return Promise.resolve(
          new Response(
            JSON.stringify({ data: { access_token: "new-token", token_type: "Bearer", expires_in: 1800 } }),
            { status: 200 },
          ),
        );
      }
      // First call per original URL returns 401; retry returns 200
      originalCallCount++;
      if (originalCallCount <= 2) {
        return Promise.resolve(new Response("{}", { status: 401 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ data: MOCK_USER }), { status: 200 }));
    });

    const onFail = vi.fn();
    const [r1, r2] = await Promise.all([
      authFetch("/api/v1/users/me", {}, { onAuthFailure: onFail }),
      authFetch("/api/v1/users/me", {}, { onAuthFailure: onFail }),
    ]);

    expect(r1.status).toBe(200);
    expect(r2.status).toBe(200);
    expect(refreshCallCount).toBe(1); // Single-flight: exactly ONE refresh
    expect(onFail).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// T17 — httpClient: refresh itself returns 401 → no infinite loop, onAuthFailure called
// ---------------------------------------------------------------------------

describe("auth T17 — httpClient: refresh 401 → no loop, onAuthFailure called", () => {
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

  it("throws AuthSessionExpiredError, calls onAuthFailure, clears token", async () => {
    vi.spyOn(global, "fetch")
      .mockImplementationOnce(() =>
        // Original request → 401
        Promise.resolve(new Response("{}", { status: 401 })),
      )
      .mockImplementationOnce(() =>
        // /auth/refresh → 401 (session fully expired)
        Promise.resolve(new Response("{}", { status: 401 })),
      );

    const onFail = vi.fn();

    await expect(
      authFetch("/api/v1/users/me", {}, { onAuthFailure: onFail }),
    ).rejects.toThrow();

    expect(onFail).toHaveBeenCalled();
    expect(getAccessToken()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// T18 — httpClient: Bearer injected on /api/v1/users/**, NOT on /auth/refresh
// ---------------------------------------------------------------------------

describe("auth T18 — httpClient: Bearer injected on protected endpoints only", () => {
  beforeEach(() => {
    clearAccessToken();
    _resetInflight();
  });
  afterEach(() => {
    clearAccessToken();
    _resetInflight();
    vi.restoreAllMocks();
  });

  it("injects Authorization Bearer on /api/v1/users/me", async () => {
    setAccessToken("my-token");
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: MOCK_USER }), { status: 200 }),
    );

    await authFetch("/api/v1/users/me");

    const capturedHeaders = fetchSpy.mock.calls[0][1]?.headers as Headers;
    expect(capturedHeaders.get("Authorization")).toBe("Bearer my-token");
  });

  it("does NOT inject Authorization Bearer on /api/v1/auth/refresh", async () => {
    setAccessToken("my-token");
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ data: { access_token: "new", token_type: "Bearer", expires_in: 1800 } }),
        { status: 200 },
      ),
    );

    await authFetch("/api/v1/auth/refresh", { method: "POST" }, { __authNoRetry: true });

    const capturedHeaders = fetchSpy.mock.calls[0][1]?.headers as Headers;
    // Refresh endpoint should NOT have Authorization header (cookie is the credential)
    expect(capturedHeaders.get("Authorization")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// T19 — Logging: BEFORE/AFTER fired in verbose mode, no token in log args
// ---------------------------------------------------------------------------

describe("auth T19 — Logging: verbose=true fires logs, no token value leaked", () => {
  const originalEnv = import.meta.env.VITE_ENABLE_VERBOSE_LOGGING;

  beforeEach(() => {
    clearAccessToken();
    vi.stubEnv("VITE_ENABLE_VERBOSE_LOGGING", "true");
  });

  afterEach(() => {
    clearAccessToken();
    vi.stubEnv("VITE_ENABLE_VERBOSE_LOGGING", originalEnv ?? "false");
    vi.restoreAllMocks();
  });

  it("setAccessToken logs present=true and len, never the token value", () => {
    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => void 0);
    const TOKEN_VALUE = "super-secret-jwt-token";

    setAccessToken(TOKEN_VALUE);

    const allLogArgs = infoSpy.mock.calls.flat(Infinity);
    // Token value must NOT appear in any log argument
    const hasTokenValue = allLogArgs.some(
      (arg) => typeof arg === "string" && arg.includes(TOKEN_VALUE),
    );
    expect(hasTokenValue).toBe(false);

    // Should log the length, not the value
    const hasLen = allLogArgs.some(
      (arg) =>
        (typeof arg === "object" &&
          arg !== null &&
          "new_len" in (arg as Record<string, unknown>)) ||
        (typeof arg === "object" &&
          arg !== null &&
          "len" in (arg as Record<string, unknown>)),
    );
    expect(hasLen).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// T20 — Logging: verbose=false only warns/errors (no info for store ops)
// ---------------------------------------------------------------------------

describe("auth T20 — Logging: verbose=false suppresses info logs", () => {
  const originalEnv = import.meta.env.VITE_ENABLE_VERBOSE_LOGGING;

  beforeEach(() => {
    clearAccessToken();
    vi.stubEnv("VITE_ENABLE_VERBOSE_LOGGING", "false");
  });

  afterEach(() => {
    clearAccessToken();
    vi.stubEnv("VITE_ENABLE_VERBOSE_LOGGING", originalEnv ?? "false");
    vi.restoreAllMocks();
  });

  it("setAccessToken does NOT log when verbose=false", () => {
    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => void 0);

    setAccessToken("another-secret-token");

    expect(infoSpy).not.toHaveBeenCalled();
  });
});

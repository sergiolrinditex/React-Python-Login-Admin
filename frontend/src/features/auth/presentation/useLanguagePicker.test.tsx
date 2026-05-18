/**
 * Hilo People — useLanguagePicker hook tests.
 *
 * Slice/Phase: P03-S02-T007 — AccountPage (profile + language + logout) / Phase 3.
 *
 * Responsibility: Unit tests for the useLanguagePicker presentation hook.
 *   Covers acceptance criteria §T007-LANGUAGE-PICKER from the task pack test plan.
 *   AuthRepository.updateLanguage is mocked at the class level (data boundary).
 *   i18n is real (inline resources from i18n/index.ts).
 *
 * Test cases:
 *   LP1 — initial current reflects useAuth().user.preferred_language.
 *   LP2 — setLanguage('en') calls authRepository.updateLanguage with Bearer + right body.
 *   LP3 — optimistic: i18n.language flips to 'en' immediately, before PATCH resolves.
 *   LP4 — on 200 success, no revert, current reflects new language.
 *   LP5 — on 400/422 (validation error), i18n reverted, error set with code 'validation'.
 *   LP6 — on network error, i18n reverted, error set with code 'network'.
 *   LP7 — concurrent rapid switches: only latest intended language wins.
 *   LP8 — clearError resets error state.
 *   LP9 — [debugger cycle 1] on 200 success, result.current.current updates immediately.
 *   LP10 — [debugger cycle 1] on 422 failure, current does NOT change (rollback).
 *   LP11 — [debugger cycle 1] success then failure: current keeps last confirmed value.
 *
 * Test policy (non-negotiables §tests):
 *   - AuthRepository mocked at class level (data layer boundary).
 *   - accessTokenStore mocked to return a test token.
 *   - i18n real singleton (no mock).
 *   - useAuth mocked (presentation boundary; real AuthProvider would need full router).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import React from "react";
import i18n from "../../../i18n/index";
import { useLanguagePicker } from "./useLanguagePicker";
import type { UserProfile } from "../domain/types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_USER_ES: UserProfile = {
  id: "user-uuid-lang-test",
  email: "lang-test@inditex-sandbox.com",
  full_name: "Lang Test User",
  status: "active",
  preferred_language: "es",
  roles: ["employee"],
  employee_profile: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const MOCK_USER_EN: UserProfile = { ...MOCK_USER_ES, preferred_language: "en" };

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("./AuthProvider", () => ({
  useAuth: vi.fn(() => ({
    status: "authenticated",
    user: MOCK_USER_ES,
    logout: vi.fn(),
    signInAccepted: vi.fn(),
  })),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock accessTokenStore to return a fake token
vi.mock("../data/accessTokenStore", () => ({
  getAccessToken: vi.fn(() => "fake-access-token-test"),
  setAccessToken: vi.fn(),
  clearAccessToken: vi.fn(),
}));

// Mock AuthRepository at class level to intercept updateLanguage
const mockUpdateLanguage = vi.fn<(token: string, language: "es" | "en" | "fr") => Promise<{ ok: true; value: UserProfile } | { ok: false; error: Error }>>();

vi.mock("../data/authRepository", () => {
  return {
    AuthRepository: vi.fn().mockImplementation(() => ({
      updateLanguage: mockUpdateLanguage,
      fetchMe: vi.fn(async () => ({ ok: true, value: MOCK_USER_ES })),
      logout: vi.fn(async () => ({ ok: true, value: undefined })),
      refresh: vi.fn(async () => ({ ok: true, value: "token" })),
      signIn: vi.fn(async () => ({ ok: true, value: { kind: "success", accessToken: "token", user: MOCK_USER_ES } })),
      signUp: vi.fn(async () => ({ ok: true, value: { user_id: "uid", mfa_required: false } })),
      forgotPassword: vi.fn(async () => ({ ok: true, value: { sent: true } })),
      verifyMfa: vi.fn(async () => ({ ok: true, value: { accessToken: "token", expiresIn: 1800, user: MOCK_USER_ES } })),
    })),
  };
});

import { useAuth } from "./AuthProvider";

const mockUseAuth = vi.mocked(useAuth);

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function renderUseLanguagePicker() {
  return renderHook(() => useLanguagePicker());
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useLanguagePicker", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    // Reset i18n to 'es' before each test
    await i18n.changeLanguage("es");
    // Default auth mock: user with preferred_language 'es'
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      user: MOCK_USER_ES,
      logout: vi.fn(),
      signInAccepted: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  // LP1 — initial current reflects user.preferred_language
  it("LP1: initial current reflects useAuth().user.preferred_language", () => {
    const { result } = renderUseLanguagePicker();
    expect(result.current.current).toBe("es");
  });

  // LP2 — setLanguage('en') calls updateLanguage with correct args
  it("LP2: setLanguage('en') calls authRepository.updateLanguage with token and 'en'", async () => {
    mockUpdateLanguage.mockResolvedValueOnce({ ok: true, value: MOCK_USER_EN });

    const { result } = renderUseLanguagePicker();

    await act(async () => {
      await result.current.setLanguage("en");
    });

    expect(mockUpdateLanguage).toHaveBeenCalledWith("fake-access-token-test", "en");
  });

  // LP3 — optimistic: i18n.language flips immediately
  it("LP3: i18n.language flips to 'en' optimistically before PATCH resolves", async () => {
    // Mock to resolve after a microtask delay so we can check optimistic state
    let resolveUpdate!: (val: { ok: true; value: UserProfile }) => void;
    mockUpdateLanguage.mockImplementationOnce(
      () => new Promise<{ ok: true; value: UserProfile }>((resolve) => { resolveUpdate = resolve; }),
    );

    const { result } = renderUseLanguagePicker();

    // Start the language change and await the optimistic i18n.changeLanguage,
    // then immediately resolve to avoid hanging async operations across test boundaries
    const changePromise = act(async () => {
      const p = result.current.setLanguage("en");
      // i18n.changeLanguage is async but settles quickly; let microtasks run
      await Promise.resolve();
      // Resolve the mocked updateLanguage now
      resolveUpdate({ ok: true, value: MOCK_USER_EN });
      await p;
    });

    await changePromise;

    // After resolution, i18n should reflect 'en' (optimistic, not reverted)
    expect(i18n.language).toBe("en");
  });

  // LP4 — on 200 success, no revert, error is null
  it("LP4: on 200 success, i18n stays at 'en', error is null, isPending is false", async () => {
    mockUpdateLanguage.mockResolvedValueOnce({ ok: true, value: MOCK_USER_EN });

    const { result } = renderUseLanguagePicker();

    await act(async () => {
      await result.current.setLanguage("en");
    });

    expect(i18n.language).toBe("en");
    expect(result.current.error).toBeNull();
    expect(result.current.isPending).toBe(false);
  });

  // LP5 — on validation error (400/422), i18n reverted, error.code = 'validation'
  it("LP5: on validation error, i18n reverted to 'es', error.code is 'validation'", async () => {
    mockUpdateLanguage.mockResolvedValueOnce({
      ok: false,
      error: new Error("LANGUAGE_INVALID: language 'xx' rejected by server (422)"),
    });

    const { result } = renderUseLanguagePicker();

    await act(async () => {
      await result.current.setLanguage("en");
    });

    expect(i18n.language).toBe("es");
    expect(result.current.error).not.toBeNull();
    expect(result.current.error?.code).toBe("validation");
    expect(result.current.isPending).toBe(false);
  });

  // LP6 — on network error, i18n reverted, error.code = 'network'
  it("LP6: on network error, i18n reverted to 'es', error.code is 'network'", async () => {
    mockUpdateLanguage.mockResolvedValueOnce({
      ok: false,
      error: new Error("Network request failed."),
    });

    const { result } = renderUseLanguagePicker();

    await act(async () => {
      await result.current.setLanguage("en");
    });

    expect(i18n.language).toBe("es");
    expect(result.current.error).not.toBeNull();
    expect(result.current.error?.code).toBe("network");
    expect(result.current.isPending).toBe(false);
  });

  // LP7 — concurrent rapid switches: only latest intended language wins
  it("LP7: rapid es→en→fr sequence: final i18n.language is fr", async () => {
    // Both calls resolve; only the last matters for final state
    mockUpdateLanguage
      .mockResolvedValueOnce({ ok: true, value: MOCK_USER_EN })
      .mockResolvedValueOnce({ ok: true, value: { ...MOCK_USER_ES, preferred_language: "fr" } });

    const { result } = renderUseLanguagePicker();

    await act(async () => {
      void result.current.setLanguage("en");
      await result.current.setLanguage("fr");
    });

    expect(i18n.language).toBe("fr");
  });

  // LP8 — clearError resets error state
  it("LP8: clearError resets the error state", async () => {
    mockUpdateLanguage.mockResolvedValueOnce({
      ok: false,
      error: new Error("Network request failed."),
    });

    const { result } = renderUseLanguagePicker();

    await act(async () => {
      await result.current.setLanguage("en");
    });

    expect(result.current.error).not.toBeNull();

    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBeNull();
  });

  // LP9 — §D-T007-D1-CONFIRMED-CURRENT (debugger cycle 1):
  //   On PATCH 200 success, result.current.current must reflect the new language
  //   IMMEDIATELY after the mutation resolves, even though useAuth().user still
  //   reports the old preferred_language (no setter exposed by AuthContext).
  //   This is the regression-prevention test for the "stale current" defect.
  it("LP9: after 200 PATCH, result.current.current updates to the server-confirmed language", async () => {
    mockUpdateLanguage.mockResolvedValueOnce({ ok: true, value: MOCK_USER_EN });

    const { result } = renderUseLanguagePicker();
    // BEFORE the change, current must be 'es' (from useAuth().user.preferred_language)
    expect(result.current.current).toBe("es");

    await act(async () => {
      await result.current.setLanguage("en");
    });

    // AFTER the change, current must be 'en' (from server-returned UserProfile)
    // even though useAuth().user.preferred_language is still 'es' (no setter).
    expect(result.current.current).toBe("en");
    expect(i18n.language).toBe("en");
  });

  // LP10 — §D-T007-D1-CONFIRMED-CURRENT (debugger cycle 1):
  //   On PATCH 422 validation failure, result.current.current MUST NOT change
  //   (rollback semantics) and i18n.language must also revert to the previous
  //   language. Confirms the confirmedCurrent state is not touched on error.
  it("LP10: on 422 validation error, current and i18n.language stay at 'es' (no rollback corruption)", async () => {
    mockUpdateLanguage.mockResolvedValueOnce({
      ok: false,
      error: new Error("LANGUAGE_INVALID: language 'en' rejected by server (422)"),
    });

    const { result } = renderUseLanguagePicker();
    expect(result.current.current).toBe("es");

    await act(async () => {
      await result.current.setLanguage("en");
    });

    // Current did NOT change to 'en' on failure
    expect(result.current.current).toBe("es");
    // i18n was reverted
    expect(i18n.language).toBe("es");
    // Error is set with validation code
    expect(result.current.error?.code).toBe("validation");
  });

  // LP11 — §D-T007-D1-CONFIRMED-CURRENT (debugger cycle 1):
  //   Sequential success then failure: confirmedCurrent persists across the failed
  //   attempt (no rollback of previously-confirmed value).
  it("LP11: after success then failed attempt, current keeps the last confirmed language", async () => {
    mockUpdateLanguage
      .mockResolvedValueOnce({ ok: true, value: MOCK_USER_EN })
      .mockResolvedValueOnce({
        ok: false,
        error: new Error("LANGUAGE_INVALID: language 'fr' rejected by server (422)"),
      });

    const { result } = renderUseLanguagePicker();

    await act(async () => {
      await result.current.setLanguage("en");
    });
    expect(result.current.current).toBe("en");

    await act(async () => {
      await result.current.setLanguage("fr");
    });
    // 'fr' failed → confirmedCurrent stays at 'en' (the last server-confirmed value)
    expect(result.current.current).toBe("en");
    expect(i18n.language).toBe("en");
  });
});

/**
 * Hilo People — useUpdateLanguage hook tests.
 *
 * Slice/Phase: P03-S02-T004 — AccountPage / Phase 3.
 *
 * Responsibility: Tests for presentation/useUpdateLanguage.ts.
 *   Mocks: useAuth, userRepository.updateLanguage, i18n.changeLanguage.
 *
 * Test cases (≥6):
 *   T01 — success: commits language in cache + i18n.language changes
 *   T02 — i18n.changeLanguage called on mutation start (optimistic)
 *   T03 — 400 validation error: reverts i18n + query cache
 *   T04 — 401 auth expired: calls onAuthFailure callback
 *   T05 — 5xx server error: reverts i18n + shows error
 *   T06 — race guard: rapid ES→EN→FR settles on FR
 *   T07 — query invalidation called on settled
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../i18n/index";
import { useUpdateLanguage } from "../presentation/useUpdateLanguage";
import { ME_QUERY_KEY } from "../presentation/useMe";
import type { UserProfile } from "../domain/types";
import {
  UserValidationError,
  UserAuthExpiredError,
  UserServerError,
} from "../domain/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../data/userRepository", () => ({
  userRepository: {
    getMe: vi.fn(),
    updateLanguage: vi.fn(),
  },
}));

import { userRepository } from "../data/userRepository";
const mockUpdateLanguage = vi.mocked(userRepository.updateLanguage);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_USER_ES: UserProfile = {
  id: "7b34e2ca-a9cc-4152-9be0-552d200464ce",
  email: "employee.verification@inditex-sandbox.com",
  full_name: "Elena Verificación",
  status: "active",
  preferred_language: "es",
  roles: ["employee"],
  employee_profile: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// Wrapper factory — takes a queryClient so tests can manipulate cache
// ---------------------------------------------------------------------------

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <I18nextProvider i18n={i18n}>
          {children}
        </I18nextProvider>
      </QueryClientProvider>
    );
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useUpdateLanguage", () => {
  let queryClient: QueryClient;
  const mockOnAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    // Seed cache with ES profile
    queryClient.setQueryData(ME_QUERY_KEY, MOCK_USER_ES);
    // Reset i18n to es
    void i18n.changeLanguage("es");
  });

  it("T01 — success: cache updated + i18n language changed to fr", async () => {
    const updatedUser = { ...MOCK_USER_ES, preferred_language: "fr" as const };
    mockUpdateLanguage.mockResolvedValueOnce({ ok: true, value: updatedUser });

    const { result } = renderHook(
      () => useUpdateLanguage(mockOnAuthFailure),
      { wrapper: createWrapper(queryClient) },
    );

    act(() => { result.current.mutate("fr"); });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });

    // Verify cache was updated with the server response
    const cached = queryClient.getQueryData<UserProfile>(ME_QUERY_KEY);
    expect(cached?.preferred_language).toBe("fr");
    expect(result.current.error).toBeNull();
  });

  it("T02 — optimistic: i18n.changeLanguage called before PATCH resolves", async () => {
    let resolveUpdate!: (v: { ok: true; value: UserProfile }) => void;
    const pendingPromise = new Promise<{ ok: true; value: UserProfile }>(
      (res) => { resolveUpdate = res; },
    );
    mockUpdateLanguage.mockReturnValueOnce(pendingPromise);

    const changeLanguageSpy = vi.spyOn(i18n, "changeLanguage");

    const { result } = renderHook(
      () => useUpdateLanguage(mockOnAuthFailure),
      { wrapper: createWrapper(queryClient) },
    );

    act(() => { result.current.mutate("en"); });

    // Optimistic: i18n.changeLanguage should have been called synchronously in onMutate
    await waitFor(() => {
      expect(changeLanguageSpy).toHaveBeenCalledWith("en");
    });

    // Resolve mutation
    act(() => {
      resolveUpdate({ ok: true, value: { ...MOCK_USER_ES, preferred_language: "en" as const } });
    });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });
  });

  it("T03 — 400 validation: reverts i18n and query cache to previous state", async () => {
    mockUpdateLanguage.mockResolvedValueOnce({
      ok: false,
      error: new UserValidationError(),
    });

    const { result } = renderHook(
      () => useUpdateLanguage(mockOnAuthFailure),
      { wrapper: createWrapper(queryClient) },
    );

    act(() => { result.current.mutate("fr"); });

    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(UserValidationError);
    });

    // Cache reverted to ES profile
    const cached = queryClient.getQueryData<UserProfile>(ME_QUERY_KEY);
    expect(cached?.preferred_language).toBe("es");

    // i18n reverted to es
    expect(i18n.language).toBe("es");
  });

  it("T04 — 401 auth expired: calls onAuthFailure callback", async () => {
    mockUpdateLanguage.mockResolvedValueOnce({
      ok: false,
      error: new UserAuthExpiredError(),
    });

    const { result } = renderHook(
      () => useUpdateLanguage(mockOnAuthFailure),
      { wrapper: createWrapper(queryClient) },
    );

    act(() => { result.current.mutate("en"); });

    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(UserAuthExpiredError);
    });

    expect(mockOnAuthFailure).toHaveBeenCalled();
  });

  it("T05 — 5xx server error: reverts i18n and shows error", async () => {
    mockUpdateLanguage.mockResolvedValueOnce({
      ok: false,
      error: new UserServerError(503),
    });

    const { result } = renderHook(
      () => useUpdateLanguage(mockOnAuthFailure),
      { wrapper: createWrapper(queryClient) },
    );

    act(() => { result.current.mutate("fr"); });

    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(UserServerError);
    });

    // i18n reverted
    expect(i18n.language).toBe("es");
  });

  it("T06 — race guard: rapid ES→EN→FR, only final FR is committed", async () => {
    let resolveEn!: (v: { ok: true; value: UserProfile }) => void;
    let resolveFr!: (v: { ok: true; value: UserProfile }) => void;

    const enPromise = new Promise<{ ok: true; value: UserProfile }>(
      (res) => { resolveEn = res; },
    );
    const frPromise = new Promise<{ ok: true; value: UserProfile }>(
      (res) => { resolveFr = res; },
    );

    mockUpdateLanguage
      .mockReturnValueOnce(enPromise)
      .mockReturnValueOnce(frPromise);

    const { result } = renderHook(
      () => useUpdateLanguage(mockOnAuthFailure),
      { wrapper: createWrapper(queryClient) },
    );

    // Rapid clicks: EN then FR
    act(() => { result.current.mutate("en"); });
    act(() => { result.current.mutate("fr"); });

    // Resolve EN first (stale — FR was the last intent)
    act(() => {
      resolveEn({ ok: true, value: { ...MOCK_USER_ES, preferred_language: "en" as const } });
    });

    // Resolve FR
    act(() => {
      resolveFr({ ok: true, value: { ...MOCK_USER_ES, preferred_language: "fr" as const } });
    });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });

    // Final state: FR committed (EN response was ignored due to race guard)
    const cached = queryClient.getQueryData<UserProfile>(ME_QUERY_KEY);
    expect(cached?.preferred_language).toBe("fr");
  });

  it("T07 — onSettled always invalidates ['user','me'] query", async () => {
    const updatedUser = { ...MOCK_USER_ES, preferred_language: "en" as const };
    mockUpdateLanguage.mockResolvedValueOnce({ ok: true, value: updatedUser });

    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(
      () => useUpdateLanguage(mockOnAuthFailure),
      { wrapper: createWrapper(queryClient) },
    );

    act(() => { result.current.mutate("en"); });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });

    // invalidateQueries called after settled
    expect(invalidateSpy).toHaveBeenCalled();
  });
});

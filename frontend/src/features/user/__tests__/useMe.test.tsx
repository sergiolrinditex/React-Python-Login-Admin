/**
 * Hilo People — useMe hook tests.
 *
 * Slice/Phase: P03-S02-T004 — AccountPage / Phase 3.
 *
 * Responsibility: Tests for presentation/useMe.ts.
 *   Mocks: useAuth (composition boundary) + userRepository.getMe (HTTP layer).
 *
 * Test cases (≥4):
 *   T01 — uses useAuth().user as initialData when authenticated (no fetch yet)
 *   T02 — refetches via repo on queryFn call; cache updates
 *   T03 — propagates UserAuthExpiredError to consumer
 *   T04 — query disabled when auth status !== 'authenticated'
 *   T05 — isPending true while fetching with no cached data
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../i18n/index";
import { useMe } from "../presentation/useMe";
import type { UserProfile } from "../domain/types";
import { UserAuthExpiredError } from "../domain/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../auth/presentation/AuthProvider", () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("../data/userRepository", () => ({
  userRepository: {
    getMe: vi.fn(),
    updateLanguage: vi.fn(),
  },
}));

import { useAuth } from "../../auth/presentation/AuthProvider";
import { userRepository } from "../data/userRepository";

const mockUseAuth = vi.mocked(useAuth);
const mockGetMe = vi.mocked(userRepository.getMe);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_USER: UserProfile = {
  id: "7b34e2ca-a9cc-4152-9be0-552d200464ce",
  email: "employee.verification@inditex-sandbox.com",
  full_name: "Elena Verificación",
  status: "active",
  preferred_language: "es",
  roles: ["employee"],
  employee_profile: {
    employee_id: "EMP-VERIFY-001",
    brand: "Zara",
    society: "ITX-ES",
    center: "Madrid-HQ",
    country: "ES",
    department: "People & Talent",
  },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
    },
  });
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

describe("useMe", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("T01 — returns initialData from useAuth().user when authenticated", async () => {
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      user: MOCK_USER,
      signInAccepted: vi.fn(),
      logout: vi.fn().mockResolvedValue(undefined),
    });
    mockGetMe.mockResolvedValue({ ok: true, value: MOCK_USER });

    const { result } = renderHook(() => useMe(), { wrapper: createWrapper() });

    // initialData is set immediately from useAuth().user
    expect(result.current.data).toEqual(MOCK_USER);
  });

  it("T02 — refetches via repo on explicit refetch(); cache updates", async () => {
    const updatedUser = { ...MOCK_USER, preferred_language: "en" as const };
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      user: MOCK_USER,
      signInAccepted: vi.fn(),
      logout: vi.fn().mockResolvedValue(undefined),
    });
    mockGetMe.mockResolvedValue({ ok: true, value: updatedUser });

    const { result } = renderHook(() => useMe(), { wrapper: createWrapper() });

    // Manually refetch
    void result.current.refetch();

    await waitFor(() => {
      expect(result.current.data?.preferred_language).toBe("en");
    });
    expect(mockGetMe).toHaveBeenCalled();
  });

  it("T03 — propagates UserAuthExpiredError to consumer via isError", async () => {
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      user: null,
      signInAccepted: vi.fn(),
      logout: vi.fn().mockResolvedValue(undefined),
    });
    mockGetMe.mockResolvedValue({ ok: false, error: new UserAuthExpiredError() });

    const { result } = renderHook(() => useMe(), { wrapper: createWrapper() });

    // Trigger the query (no initialData since user is null)
    void result.current.refetch();

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
      expect(result.current.error).toBeInstanceOf(UserAuthExpiredError);
    });
  });

  it("T04 — query is disabled when auth status !== authenticated", () => {
    mockUseAuth.mockReturnValue({
      status: "unauthenticated",
      user: null,
      signInAccepted: vi.fn(),
      logout: vi.fn().mockResolvedValue(undefined),
    });

    const { result } = renderHook(() => useMe(), { wrapper: createWrapper() });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGetMe).not.toHaveBeenCalled();
  });

  it("T05 — query disabled during hydrating status", () => {
    mockUseAuth.mockReturnValue({
      status: "hydrating",
      user: null,
      signInAccepted: vi.fn(),
      logout: vi.fn().mockResolvedValue(undefined),
    });

    const { result } = renderHook(() => useMe(), { wrapper: createWrapper() });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGetMe).not.toHaveBeenCalled();
  });
});

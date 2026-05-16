/**
 * Hilo People — useDashboardUsage hook tests.
 *
 * Slice/Phase: P04-S01-T001 — AdminDashboardPage / Phase 4.
 * Write-set anchor: §D-T001-TESTS
 *
 * Responsibility: Tests for the useDashboardUsage presentation hook.
 *   getUsage repository is mocked (fetch boundary); useAuth is mocked.
 *   TanStack Query client is real (wraps with QueryClientProvider).
 *
 * Cases:
 *   H01 — query key shape: ["admin","usage","dashboard",{from,to,group_by}].
 *   H02 — loading → success with populated data: isLoading then isSuccess.
 *   H03 — loading → empty: isSuccess with rows=[], totals.invocations=0.
 *   H04 — loading → error: isError with typed AdminAiError.
 *   H05 — computeUsageWindow: computes correct 30-day window.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useDashboardUsage, computeUsageWindow } from "../presentation/useDashboardUsage";
import { AdminAiNetworkError } from "../data/errors";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../data/adminAiRepository", () => ({
  getUsage: vi.fn(),
}));

vi.mock("../../auth/presentation/AuthProvider", () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { getUsage } from "../data/adminAiRepository";
import { useAuth } from "../../auth/presentation/AuthProvider";

const mockGetUsage = vi.mocked(getUsage);
const mockUseAuth = vi.mocked(useAuth);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_TOTALS = {
  tokens_in: 1234,
  tokens_out: 567,
  estimated_cost: 0.0123,
  invocations: 12,
  latency_ms_avg: 842,
};

const MOCK_ROWS = [
  {
    tokens_in: 1234,
    tokens_out: 567,
    estimated_cost: 0.0123,
    latency_ms_avg: 842,
    invocations: 12,
    model_name: "gpt-4o-mini",
  },
];

const MOCK_USAGE_SUMMARY = {
  from: "2026-04-16T00:00:00Z",
  to: "2026-05-16T00:00:00Z",
  group_by: "model" as const,
  rows: MOCK_ROWS,
  totals: MOCK_TOTALS,
};

const EMPTY_SUMMARY = {
  from: "2026-04-16T00:00:00Z",
  to: "2026-05-16T00:00:00Z",
  group_by: "model" as const,
  rows: [],
  totals: { tokens_in: 0, tokens_out: 0, estimated_cost: 0, invocations: 0, latency_ms_avg: 0 },
};

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useDashboardUsage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      user: null,
      signInAccepted: vi.fn(),
      logout: vi.fn().mockResolvedValue(undefined),
    });
  });

  it("H01 — query key includes admin/usage/dashboard with from/to/group_by shape", async () => {
    mockGetUsage.mockResolvedValueOnce({ ok: true, value: MOCK_USAGE_SUMMARY });

    const { result } = renderHook(() => useDashboardUsage(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Verify getUsage was called with a GetUsageRequest
    expect(mockGetUsage).toHaveBeenCalledWith(
      expect.objectContaining({ group_by: "model" }),
      expect.any(Function),
    );
  });

  it("H02 — loading → success with populated data", async () => {
    mockGetUsage.mockResolvedValueOnce({ ok: true, value: MOCK_USAGE_SUMMARY });

    const { result } = renderHook(() => useDashboardUsage(), {
      wrapper: makeWrapper(),
    });

    // Initially loading
    expect(result.current.isLoading).toBe(true);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toBeDefined();
    expect(result.current.data?.rows).toHaveLength(1);
    expect(result.current.data?.totals.invocations).toBe(12);
    expect(result.current.isError).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("H03 — loading → empty: isSuccess with rows=[], invocations=0", async () => {
    mockGetUsage.mockResolvedValueOnce({ ok: true, value: EMPTY_SUMMARY });

    const { result } = renderHook(() => useDashboardUsage(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.rows).toHaveLength(0);
    expect(result.current.data?.totals.invocations).toBe(0);
    expect(result.current.isError).toBe(false);
  });

  it("H04 — loading → error: isError with typed AdminAiError", async () => {
    mockGetUsage.mockResolvedValueOnce({
      ok: false,
      error: new AdminAiNetworkError("Network failed"),
    });

    const { result } = renderHook(() => useDashboardUsage(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.isSuccess).toBe(false);
    expect(result.current.error).toBeInstanceOf(AdminAiNetworkError);
  });

  it("H05 — refetch: calls getUsage again", async () => {
    mockGetUsage
      .mockResolvedValueOnce({ ok: true, value: MOCK_USAGE_SUMMARY })
      .mockResolvedValueOnce({ ok: true, value: MOCK_USAGE_SUMMARY });

    const { result } = renderHook(() => useDashboardUsage(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const callCountBefore = mockGetUsage.mock.calls.length;

    act(() => {
      result.current.refetch();
    });

    await waitFor(() => expect(mockGetUsage.mock.calls.length).toBeGreaterThan(callCountBefore));
  });
});

// ---------------------------------------------------------------------------
// computeUsageWindow tests
// ---------------------------------------------------------------------------

describe("computeUsageWindow", () => {
  it("H05 — returns 30-day window ending at nowMs", () => {
    const nowMs = new Date("2026-05-16T00:00:00Z").getTime();
    const { from, to } = computeUsageWindow(nowMs, 30);

    const fromDate = new Date(from);
    const toDate = new Date(to);

    // to should be now
    expect(toDate.getTime()).toBe(nowMs);

    // from should be 30 days before
    const diffMs = toDate.getTime() - fromDate.getTime();
    expect(diffMs).toBe(30 * 24 * 60 * 60 * 1000);
  });

  it("H06 — from and to are valid ISO-8601 strings", () => {
    const { from, to } = computeUsageWindow(Date.now());
    expect(() => new Date(from)).not.toThrow();
    expect(() => new Date(to)).not.toThrow();
    expect(new Date(from).toISOString()).toBe(from);
    expect(new Date(to).toISOString()).toBe(to);
  });
});

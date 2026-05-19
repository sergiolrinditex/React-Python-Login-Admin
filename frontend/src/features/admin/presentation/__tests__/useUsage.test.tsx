/**
 * Hilo People — useUsage hook tests.
 *
 * Slice/Phase: P04-S03-T002 — UsagePage / Phase 4 Complete Features.
 *
 * Responsibility: Tests for the useUsage TanStack v5 useQuery hook.
 *   Covers: loading→success, error propagation, range invariant disabled,
 *   and refetch trigger.
 *   Each test creates a fresh QueryClient to prevent state bleed.
 *
 * Pattern: React Testing Library + @testing-library/react + TanStack Query v5.
 * Mocks: getUsage (data layer boundary — unit test of hook logic).
 *
 * Non-negotiables: tests are REAL for the hook's internal logic;
 *   only the data layer (getUsage) is mocked (owned boundary).
 *
 * D-T002-TEST-HOOK: Canonical write_set anchor for this file.
 * Source ref: §D-T002-TEST-HOOK, task pack §12 AC4.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useUsage, isRangeValid } from "../useUsage";
import {
  UsageForbiddenError,
  UsageNetworkError,
} from "../../data/errors";
import type { UsageSummary } from "../../domain/types";

// ---------------------------------------------------------------------------
// Mock data layer
// ---------------------------------------------------------------------------

vi.mock("../../data/usageRepository", () => ({
  getUsage: vi.fn(),
}));

// Mock useAuth (AuthProvider dependency)
vi.mock("../../../auth/presentation/AuthProvider", () => ({
  useAuth: () => ({ logout: vi.fn() }),
}));

import { getUsage } from "../../data/usageRepository";

const mockGetUsage = getUsage as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEFAULT_FROM = new Date("2026-04-16T00:00:00Z");
const DEFAULT_TO = new Date("2026-05-16T00:00:00Z");

const MOCK_SUMMARY: UsageSummary = {
  from: "2026-04-16T00:00:00+00:00",
  to: "2026-05-16T00:00:00+00:00",
  group_by: "model_day",
  rows: [
    {
      model_id: "uuid-1",
      model_name: "gpt-4o",
      provider_type: "openai",
      day: "2026-05-15",
      tokens_in: 1000,
      tokens_out: 500,
      estimated_cost: 0.025,
      latency_ms_avg: 1200,
      invocations: 5,
    },
  ],
  totals: {
    tokens_in: 1000,
    tokens_out: 500,
    estimated_cost: 0.025,
    latency_ms_avg: 1200,
    invocations: 5,
  },
};

/** Creates a fresh QueryClient for each test. */
function makeWrapper(): ({ children }: { children: ReactNode }) => ReactNode {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false, // disable retries in tests
        gcTime: 0,
      },
    },
  });
  return ({ children }) =>
    (<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>) as ReactNode;
}

// ---------------------------------------------------------------------------
// isRangeValid unit tests
// ---------------------------------------------------------------------------

describe("isRangeValid", () => {
  it("useUsage: returns true for valid 30-day range", () => {
    const from = new Date("2026-04-16T00:00:00Z");
    const to = new Date("2026-05-16T00:00:00Z");
    expect(isRangeValid(from, to)).toBe(true);
  });

  it("useUsage: returns false when from >= to", () => {
    const same = new Date("2026-05-01T00:00:00Z");
    expect(isRangeValid(same, same)).toBe(false);
    const from = new Date("2026-05-02T00:00:00Z");
    const to = new Date("2026-05-01T00:00:00Z");
    expect(isRangeValid(from, to)).toBe(false);
  });

  it("useUsage: returns false when range > 90 days", () => {
    const from = new Date("2026-01-01T00:00:00Z");
    const to = new Date("2026-04-02T00:00:00Z"); // 91 days
    expect(isRangeValid(from, to)).toBe(false);
  });

  it("useUsage: returns true for exactly 90 days", () => {
    const from = new Date("2026-01-01T00:00:00Z");
    const to = new Date("2026-04-01T00:00:00Z"); // 90 days exactly
    expect(isRangeValid(from, to)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// useUsage hook tests
// ---------------------------------------------------------------------------

describe("useUsage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("useUsage: loading→success resolves data when getUsage returns ok", async () => {
    mockGetUsage.mockResolvedValueOnce({ ok: true, value: MOCK_SUMMARY });

    const { result } = renderHook(
      () => useUsage({ from: DEFAULT_FROM, to: DEFAULT_TO, groupBy: "model_day" }),
      { wrapper: makeWrapper() },
    );

    // Initially pending
    expect(result.current.isPending).toBe(true);

    // Wait for resolution
    await waitFor(() => expect(result.current.isPending).toBe(false));

    expect(result.current.data).toBeDefined();
    expect(result.current.data?.rows).toHaveLength(1);
    expect(result.current.error).toBeNull();
  });

  it("useUsage: invalid range → isRangeInvalid=true, no fetch triggered", async () => {
    const from = new Date("2026-05-16T00:00:00Z");
    const to = new Date("2026-04-16T00:00:00Z"); // to < from

    const { result } = renderHook(
      () => useUsage({ from, to, groupBy: "model_day" }),
      { wrapper: makeWrapper() },
    );

    // Should not fetch; isPending false because enabled=false
    expect(result.current.isRangeInvalid).toBe(true);
    expect(result.current.isPending).toBe(false);
    expect(mockGetUsage).not.toHaveBeenCalled();
  });

  it("useUsage: error propagation — forbidden error surfaces in result", async () => {
    const forbiddenErr = new UsageForbiddenError();
    // Hook has retry:1 so TanStack calls queryFn up to 2 times; mock both responses
    mockGetUsage
      .mockResolvedValueOnce({ ok: false, error: forbiddenErr })
      .mockResolvedValueOnce({ ok: false, error: forbiddenErr });

    const { result } = renderHook(
      () => useUsage({ from: DEFAULT_FROM, to: DEFAULT_TO, groupBy: "model_day" }),
      { wrapper: makeWrapper() },
    );

    // Wait until TanStack completes all retries (error state, not pending)
    await waitFor(() => expect(result.current.error).not.toBeNull(), { timeout: 5000 });

    expect(result.current.error).toBeInstanceOf(UsageForbiddenError);
    expect(result.current.data).toBeUndefined();
  });

  it("useUsage: network error surfaces correctly", async () => {
    const netErr = new UsageNetworkError("Network failed");
    // Hook has retry:1 so TanStack calls queryFn up to 2 times; mock both responses
    mockGetUsage
      .mockResolvedValueOnce({ ok: false, error: netErr })
      .mockResolvedValueOnce({ ok: false, error: netErr });

    const { result } = renderHook(
      () => useUsage({ from: DEFAULT_FROM, to: DEFAULT_TO, groupBy: "model_day" }),
      { wrapper: makeWrapper() },
    );

    // Wait until TanStack completes all retries (error state, not pending)
    await waitFor(() => expect(result.current.error).not.toBeNull(), { timeout: 5000 });

    expect(result.current.error).toBeInstanceOf(UsageNetworkError);
  });

  it("useUsage: refetch function triggers an additional query call", async () => {
    // Success on first call, success on refetch call
    mockGetUsage
      .mockResolvedValueOnce({ ok: true, value: MOCK_SUMMARY })
      .mockResolvedValueOnce({ ok: true, value: MOCK_SUMMARY });

    const { result } = renderHook(
      () => useUsage({ from: DEFAULT_FROM, to: DEFAULT_TO, groupBy: "model_day" }),
      { wrapper: makeWrapper() },
    );

    // Wait for initial load
    await waitFor(() => expect(result.current.data).toBeDefined());

    const callsBefore = mockGetUsage.mock.calls.length;

    act(() => {
      result.current.refetch();
    });

    // After refetch, at least one more call should happen
    await waitFor(() => expect(mockGetUsage.mock.calls.length).toBeGreaterThan(callsBefore));
  });
});

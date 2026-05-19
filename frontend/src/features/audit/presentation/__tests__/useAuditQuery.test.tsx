/**
 * Hilo People — useAuditQuery hook tests.
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: Tests for the useAuditQuery TanStack v5 useQuery hook.
 *   Covers: loading→success, error propagation, range invariant disabled,
 *   actor validation, and refetch trigger.
 *   Each test creates a fresh QueryClient to prevent state bleed.
 *
 * Pattern: React Testing Library + @testing-library/react + TanStack Query v5.
 * Mocks: getAuditPage (data layer boundary — unit test of hook logic).
 *
 * §D-T001-TESTS: Canonical write_set anchor for this file.
 * Source ref: §D-T001-TESTS, task pack §16 AC6.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useAuditQuery, isAuditRangeValid, isActorValid } from "../useAuditQuery";
import {
  AuditForbiddenError,
  AuditNetworkError,
} from "../../data/errors";
import type { AuditPage } from "../../domain/types";

// ---------------------------------------------------------------------------
// Mock data layer
// ---------------------------------------------------------------------------

vi.mock("../../data/auditRepository", () => ({
  getAuditPage: vi.fn(),
}));

// Mock useAuth (AuthProvider dependency)
vi.mock("../../../auth/presentation/AuthProvider", () => ({
  useAuth: () => ({ logout: vi.fn() }),
}));

import { getAuditPage } from "../../data/auditRepository";

const mockGetAuditPage = getAuditPage as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEFAULT_FROM = new Date("2026-05-12T00:00:00Z");
const DEFAULT_TO = new Date("2026-05-19T23:59:59Z");

const MOCK_AUDIT_PAGE: AuditPage = {
  rows: [
    {
      id: "row-1",
      actor_user_id: "actor-uuid-1",
      action: "auth.sign_in",
      entity_type: "user",
      entity_id: null,
      metadata: { request_id: "req-1" },
      created_at: "2026-05-19T10:00:00Z",
    },
  ],
  next_cursor: null,
  has_more: false,
  count: 1,
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
// isAuditRangeValid unit tests
// ---------------------------------------------------------------------------

describe("isAuditRangeValid", () => {
  it("useAuditQuery: returns true for valid 7-day range", () => {
    const from = new Date("2026-05-12T00:00:00Z");
    const to = new Date("2026-05-19T00:00:00Z");
    expect(isAuditRangeValid(from, to)).toBe(true);
  });

  it("useAuditQuery: returns false when from >= to", () => {
    const same = new Date("2026-05-19T00:00:00Z");
    expect(isAuditRangeValid(same, same)).toBe(false);
    const from = new Date("2026-05-20T00:00:00Z");
    const to = new Date("2026-05-19T00:00:00Z");
    expect(isAuditRangeValid(from, to)).toBe(false);
  });

  it("useAuditQuery: returns false when range > 90 days", () => {
    const from = new Date("2026-01-01T00:00:00Z");
    const to = new Date("2026-04-02T00:00:00Z"); // 91 days
    expect(isAuditRangeValid(from, to)).toBe(false);
  });

  it("useAuditQuery: returns true for exactly 90 days", () => {
    const from = new Date("2026-01-01T00:00:00Z");
    const to = new Date("2026-04-01T00:00:00Z"); // 90 days exactly
    expect(isAuditRangeValid(from, to)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// isActorValid unit tests
// ---------------------------------------------------------------------------

describe("isActorValid", () => {
  it("isActorValid: returns true for empty string", () => {
    expect(isActorValid("")).toBe(true);
    expect(isActorValid(undefined)).toBe(true);
  });

  it("isActorValid: returns true for valid UUID", () => {
    expect(isActorValid("550e8400-e29b-41d4-a716-446655440000")).toBe(true);
  });

  it("isActorValid: returns false for non-UUID string", () => {
    expect(isActorValid("not-a-uuid")).toBe(false);
    expect(isActorValid("user@example.com")).toBe(false);
    expect(isActorValid("12345")).toBe(false);
  });

  it("isActorValid: returns true for whitespace-only string", () => {
    expect(isActorValid("   ")).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// useAuditQuery hook tests
// ---------------------------------------------------------------------------

describe("useAuditQuery", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("useAuditQuery: loading→success resolves data when getAuditPage returns ok", async () => {
    mockGetAuditPage.mockResolvedValueOnce({ ok: true, value: MOCK_AUDIT_PAGE });

    const { result } = renderHook(
      () => useAuditQuery({ from: DEFAULT_FROM, to: DEFAULT_TO }),
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

  it("useAuditQuery: invalid range → isRangeInvalid=true, no fetch triggered", async () => {
    const from = new Date("2026-05-19T00:00:00Z");
    const to = new Date("2026-05-12T00:00:00Z"); // to < from

    const { result } = renderHook(
      () => useAuditQuery({ from, to }),
      { wrapper: makeWrapper() },
    );

    // Should not fetch; isPending false because enabled=false
    expect(result.current.isRangeInvalid).toBe(true);
    expect(result.current.isPending).toBe(false);
    expect(mockGetAuditPage).not.toHaveBeenCalled();
  });

  it("useAuditQuery: invalid actor UUID → isActorInvalid=true, no fetch triggered", async () => {
    const { result } = renderHook(
      () => useAuditQuery({ from: DEFAULT_FROM, to: DEFAULT_TO, actor: "not-a-uuid" }),
      { wrapper: makeWrapper() },
    );

    expect(result.current.isActorInvalid).toBe(true);
    expect(result.current.isPending).toBe(false);
    expect(mockGetAuditPage).not.toHaveBeenCalled();
  });

  it("useAuditQuery: error propagation — forbidden error surfaces in result", async () => {
    const forbiddenErr = new AuditForbiddenError();
    mockGetAuditPage
      .mockResolvedValueOnce({ ok: false, error: forbiddenErr })
      .mockResolvedValueOnce({ ok: false, error: forbiddenErr });

    const { result } = renderHook(
      () => useAuditQuery({ from: DEFAULT_FROM, to: DEFAULT_TO }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.error).not.toBeNull(), { timeout: 5000 });

    expect(result.current.error).toBeInstanceOf(AuditForbiddenError);
    expect(result.current.data).toBeUndefined();
  });

  it("useAuditQuery: network error surfaces correctly", async () => {
    const netErr = new AuditNetworkError("Network failed");
    mockGetAuditPage
      .mockResolvedValueOnce({ ok: false, error: netErr })
      .mockResolvedValueOnce({ ok: false, error: netErr });

    const { result } = renderHook(
      () => useAuditQuery({ from: DEFAULT_FROM, to: DEFAULT_TO }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.error).not.toBeNull(), { timeout: 5000 });

    expect(result.current.error).toBeInstanceOf(AuditNetworkError);
  });

  it("useAuditQuery: refetch function triggers an additional query call", async () => {
    mockGetAuditPage
      .mockResolvedValueOnce({ ok: true, value: MOCK_AUDIT_PAGE })
      .mockResolvedValueOnce({ ok: true, value: MOCK_AUDIT_PAGE });

    const { result } = renderHook(
      () => useAuditQuery({ from: DEFAULT_FROM, to: DEFAULT_TO }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.data).toBeDefined());

    const callsBefore = mockGetAuditPage.mock.calls.length;

    act(() => {
      result.current.refetch();
    });

    await waitFor(() => expect(mockGetAuditPage.mock.calls.length).toBeGreaterThan(callsBefore));
  });

  it("useAuditQuery: valid actor UUID passes through to query", async () => {
    mockGetAuditPage.mockResolvedValueOnce({ ok: true, value: MOCK_AUDIT_PAGE });

    const { result } = renderHook(
      () => useAuditQuery({
        from: DEFAULT_FROM,
        to: DEFAULT_TO,
        actor: "550e8400-e29b-41d4-a716-446655440000",
      }),
      { wrapper: makeWrapper() },
    );

    // Actor is valid — should NOT be flagged
    expect(result.current.isActorInvalid).toBe(false);

    await waitFor(() => expect(result.current.isPending).toBe(false));
    expect(mockGetAuditPage).toHaveBeenCalled();
  });
});

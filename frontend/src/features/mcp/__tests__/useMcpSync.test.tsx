/**
 * Hilo People — useMcpSync hook tests.
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *
 * Responsibility: Tests for useMcpSync (TanStack Query v5 useMutation wrapper).
 *   syncServer is mocked at the module boundary.
 *
 * §D-T003-TESTS-USE-SYNC (P04-S02-T003 task pack §5)
 *   S01 — mutate happy → invalidates ['admin','mcp','servers']
 *   S02 — mutate 502 → throws McpServerUnreachableError
 *   S03 — mutate 429 → throws McpRateLimitedError
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useMcpSync } from "../presentation/useMcpSync";
import { McpServerUnreachableError, McpRateLimitedError } from "../data/errors";

// ---------------------------------------------------------------------------
// Mock mcpRepository
// ---------------------------------------------------------------------------

vi.mock("../data/mcpRepository", () => ({
  syncServer: vi.fn(),
}));

import { syncServer } from "../data/mcpRepository";
const mockSyncServer = vi.mocked(syncServer);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_SYNC_RESULT = {
  tools_count: 3,
  resources_count: 1,
  prompts_count: 0,
  status: "active" as const,
};

// ---------------------------------------------------------------------------
// Test harness
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false, gcTime: 0 },
    },
  });
  return {
    queryClient,
    Wrapper: function Wrapper({ children }: { children: React.ReactNode }) {
      return React.createElement(QueryClientProvider, { client: queryClient }, children);
    },
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useMcpSync", () => {
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("S01 — mutate happy path → invalidates ['admin','mcp','servers']", async () => {
    mockSyncServer.mockResolvedValueOnce({ ok: true, value: MOCK_SYNC_RESULT });

    const { queryClient, Wrapper } = makeWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(
      () => useMcpSync(onAuthFailure),
      { wrapper: Wrapper },
    );

    await act(async () => {
      result.current.mutate({ id: "server-uuid-1" });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Verify invalidation was called with the servers query key
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["admin", "mcp", "servers"],
      }),
    );
    expect(result.current.data?.tools_count).toBe(3);
  });

  it("S02 — mutate 502 → throws McpServerUnreachableError", async () => {
    mockSyncServer.mockResolvedValueOnce({
      ok: false,
      error: new McpServerUnreachableError(),
    });

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(
      () => useMcpSync(onAuthFailure),
      { wrapper: Wrapper },
    );

    await act(async () => {
      result.current.mutate({ id: "server-uuid-1" });
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(McpServerUnreachableError);
    expect((result.current.error as McpServerUnreachableError).code).toBe("MCP_SERVER_UNREACHABLE");
  });

  it("S03 — mutate 429 → throws McpRateLimitedError", async () => {
    mockSyncServer.mockResolvedValueOnce({
      ok: false,
      error: new McpRateLimitedError(),
    });

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(
      () => useMcpSync(onAuthFailure),
      { wrapper: Wrapper },
    );

    await act(async () => {
      result.current.mutate({ id: "server-uuid-1" });
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(McpRateLimitedError);
    expect((result.current.error as McpRateLimitedError).code).toBe("MCP_RATE_LIMITED");
  });
});

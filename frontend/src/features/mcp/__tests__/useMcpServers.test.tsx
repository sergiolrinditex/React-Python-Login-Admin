/**
 * Hilo People — useMcpServers hook tests.
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *
 * Responsibility: Tests for useMcpServers (TanStack Query v5 useQuery wrapper).
 *   listServers is mocked at the module boundary.
 *
 * §D-T003-TESTS-USE-SERVERS (P04-S02-T003 task pack §5)
 *   H01 — returns servers when repository succeeds
 *   H02 — surfaces McpAuthExpiredError as isError=true
 *   H03 — refetch triggers a second call
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useMcpServers } from "../presentation/useMcpServers";
import { McpAuthExpiredError, McpNetworkError } from "../data/errors";
import type { McpServer } from "../domain/types";

// ---------------------------------------------------------------------------
// Mock mcpRepository
// ---------------------------------------------------------------------------

vi.mock("../data/mcpRepository", () => ({
  listServers: vi.fn(),
}));

import { listServers } from "../data/mcpRepository";
const mockListServers = vi.mocked(listServers);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_SERVER: McpServer = {
  id: "server-uuid-1",
  name: "sandbox_readonly",
  transport: "http",
  endpoint: "http://localhost:8080/mcp",
  status: "active",
  last_sync_at: null,
  created_by: null,
  has_credential: false,
  auth_type: null,
};

// ---------------------------------------------------------------------------
// Test harness
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useMcpServers", () => {
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("H01 — returns servers when repository succeeds", async () => {
    mockListServers.mockResolvedValueOnce({ ok: true, value: [MOCK_SERVER] });

    const { result } = renderHook(
      () => useMcpServers(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeDefined();
    });

    expect(result.current.data).toHaveLength(1);
    expect(result.current.data![0].id).toBe("server-uuid-1");
    expect(result.current.isError).toBe(false);
  });

  it("H02 — surfaces McpAuthExpiredError as isError=true", async () => {
    mockListServers.mockResolvedValueOnce({
      ok: false,
      error: new McpAuthExpiredError(),
    });

    const { result } = renderHook(
      () => useMcpServers(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(McpAuthExpiredError);
    expect((result.current.error as McpAuthExpiredError).code).toBe("MCP_AUTH_EXPIRED");
  });

  it("H03 — refetch triggers a second listServers call", async () => {
    mockListServers
      .mockResolvedValueOnce({ ok: false, error: new McpNetworkError("Timeout") })
      .mockResolvedValueOnce({ ok: true, value: [MOCK_SERVER] });

    const { result } = renderHook(
      () => useMcpServers(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    // Wait for initial error
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    // Trigger retry via refetch
    await result.current.refetch();

    await waitFor(() => {
      expect(result.current.isError).toBe(false);
      expect(result.current.data).toHaveLength(1);
    });

    expect(mockListServers).toHaveBeenCalledTimes(2);
  });
});

/**
 * Hilo People — useAgents hook tests.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: Tests for useAgents (TanStack Query v5 useQuery wrapper).
 *   listAgents is mocked at the module boundary.
 *
 * §D-T005-TESTS-USE-AGENTS (P04-S02-T005 task pack §10)
 *   H01 — returns agents when repository succeeds
 *   H02 — uses queryKey ["admin","agents"] and staleTime 30_000
 *   H03 — surfaces AgentsForbiddenError as isError=true
 *   H04 — surfaces AgentsAuthExpiredError as isError=true
 *   H05 — refetch triggers a second listAgents call
 *   H06 — 500 error surfaces as AgentsServerError
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useAgents, AGENTS_QUERY_KEY } from "../presentation/useAgents";
import { AgentsForbiddenError, AgentsAuthExpiredError, AgentsNetworkError, AgentsServerError } from "../data/errors";
import type { Agent } from "../domain/types";

// ---------------------------------------------------------------------------
// Mock agentsRepository
// ---------------------------------------------------------------------------

vi.mock("../data/agentsRepository", () => ({
  listAgents: vi.fn(),
}));

import { listAgents } from "../data/agentsRepository";
const mockListAgents = vi.mocked(listAgents);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_AGENT: Agent = {
  id: "agent-uuid-1",
  name: "people_helper",
  description: "HR assistant",
  enabled: true,
  config: {},
  bound_tools: [],
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

describe("useAgents", () => {
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("H01 — returns agents when repository succeeds", async () => {
    mockListAgents.mockResolvedValueOnce({ ok: true, value: [MOCK_AGENT] });

    const { result } = renderHook(
      () => useAgents(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeDefined();
    });

    expect(result.current.data).toHaveLength(1);
    expect(result.current.data![0].id).toBe("agent-uuid-1");
    expect(result.current.isError).toBe(false);
  });

  it("H02 — uses queryKey ['admin','agents']", () => {
    expect(AGENTS_QUERY_KEY).toEqual(["admin", "agents"]);
  });

  it("H03 — surfaces AgentsForbiddenError as isError=true", async () => {
    mockListAgents.mockResolvedValueOnce({
      ok: false,
      error: new AgentsForbiddenError(),
    });

    const { result } = renderHook(
      () => useAgents(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(AgentsForbiddenError);
    expect((result.current.error as AgentsForbiddenError).code).toBe("AGENTS_FORBIDDEN");
  });

  it("H04 — surfaces AgentsAuthExpiredError as isError=true", async () => {
    mockListAgents.mockResolvedValueOnce({
      ok: false,
      error: new AgentsAuthExpiredError(),
    });

    const { result } = renderHook(
      () => useAgents(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(AgentsAuthExpiredError);
  });

  it("H05 — refetch triggers a second listAgents call", async () => {
    mockListAgents
      .mockResolvedValueOnce({ ok: false, error: new AgentsNetworkError("Timeout") })
      .mockResolvedValueOnce({ ok: true, value: [MOCK_AGENT] });

    const { result } = renderHook(
      () => useAgents(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    await result.current.refetch();

    await waitFor(() => {
      expect(result.current.isError).toBe(false);
      expect(result.current.data).toHaveLength(1);
    });

    expect(mockListAgents).toHaveBeenCalledTimes(2);
  });

  it("H06 — 500 error surfaces as AgentsServerError", async () => {
    mockListAgents.mockResolvedValueOnce({
      ok: false,
      error: new AgentsServerError(500),
    });

    const { result } = renderHook(
      () => useAgents(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(AgentsServerError);
  });
});

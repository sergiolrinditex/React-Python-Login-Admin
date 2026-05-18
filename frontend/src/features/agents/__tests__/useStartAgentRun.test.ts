/**
 * Hilo People — useStartAgentRun hook tests.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: Tests for useStartAgentRun (TanStack Query v5 useMutation wrapper).
 *   startAgentRun is mocked at the module boundary.
 *
 * §D-T005-TESTS-USE-START-RUN (P04-S02-T005 task pack §10)
 *   S01 — mutate success returns run_id + status
 *   S02 — 409 AGENT_DISABLED → throws AgentsAgentDisabledError
 *   S03 — 502 → throws AgentsRunUnreachableError (expected dev sandbox path)
 *   S04 — mutation key is ["agents","startRun"]
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useStartAgentRun, START_AGENT_RUN_MUTATION_KEY } from "../presentation/useStartAgentRun";
import { AgentsAgentDisabledError, AgentsRunUnreachableError } from "../data/errors";

// ---------------------------------------------------------------------------
// Mock agentsRepository
// ---------------------------------------------------------------------------

vi.mock("../data/agentsRepository", () => ({
  startAgentRun: vi.fn(),
}));

import { startAgentRun } from "../data/agentsRepository";
const mockStartAgentRun = vi.mocked(startAgentRun);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_RUN_RESULT = {
  run_id: "run-uuid-1",
  status: "pending" as const,
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
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useStartAgentRun", () => {
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("S01 — mutate success returns run_id + status", async () => {
    mockStartAgentRun.mockResolvedValueOnce({ ok: true, value: MOCK_RUN_RESULT });

    const { result } = renderHook(
      () => useStartAgentRun(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await act(async () => {
      result.current.mutate({ agent_id: "agent-uuid-1", input: "ping" });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.run_id).toBe("run-uuid-1");
    expect(result.current.data?.status).toBe("pending");
  });

  it("S02 — 409 AGENT_DISABLED → throws AgentsAgentDisabledError", async () => {
    mockStartAgentRun.mockResolvedValueOnce({
      ok: false,
      error: new AgentsAgentDisabledError(),
    });

    const { result } = renderHook(
      () => useStartAgentRun(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await act(async () => {
      result.current.mutate({ agent_id: "agent-uuid-1", input: "ping" });
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(AgentsAgentDisabledError);
    expect((result.current.error as AgentsAgentDisabledError).code).toBe("AGENT_DISABLED");
  });

  it("S03 — 502 → throws AgentsRunUnreachableError (expected dev sandbox path)", async () => {
    mockStartAgentRun.mockResolvedValueOnce({
      ok: false,
      error: new AgentsRunUnreachableError(),
    });

    const { result } = renderHook(
      () => useStartAgentRun(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await act(async () => {
      result.current.mutate({ agent_id: "agent-uuid-1", input: "ping" });
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(AgentsRunUnreachableError);
    expect((result.current.error as AgentsRunUnreachableError).code).toBe("AGENT_RUN_FAILED");
  });

  it("S04 — mutation key is ['agents','startRun']", () => {
    expect(START_AGENT_RUN_MUTATION_KEY).toEqual(["agents", "startRun"]);
  });
});

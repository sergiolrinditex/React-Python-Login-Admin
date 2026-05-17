/**
 * Hilo People — useCreateMcpServer hook tests.
 *
 * Slice/Phase: P04-S02-T004 — McpWizardPage / Phase 4.
 *
 * Responsibility: Tests for useCreateMcpServer (TanStack Query v5 useMutation wrapper).
 *   createServer is mocked at the module boundary (HTTP boundary, not business logic).
 *   navigate is mocked to prevent router dependency in jsdom.
 *
 * §D-T004-TESTS-USE-CREATE (P04-S02-T004 task pack §6)
 *   C01 — mutate happy (auth=none) → invalidates servers query
 *   C02 — mutate 422 → throws McpValidationError with fieldErrors
 *   C03 — mutate 500 → throws McpServerError
 *   C04 — secret NEVER appears in result data (§D-T004-SECRET-NEVER-PERSISTED)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useCreateMcpServer } from "../presentation/useCreateMcpServer";
import { McpValidationError, McpServerError } from "../data/errors";

// ---------------------------------------------------------------------------
// Mock react-router useNavigate
// ---------------------------------------------------------------------------

const mockNavigate = vi.fn();
vi.mock("react-router", () => ({
  useNavigate: () => mockNavigate,
}));

// ---------------------------------------------------------------------------
// Mock mcpRepository.createServer at HTTP boundary
// ---------------------------------------------------------------------------

vi.mock("../data/mcpRepository", () => ({
  createServer: vi.fn(),
  listServers: vi.fn(),
  syncServer: vi.fn(),
}));

import { createServer } from "../data/mcpRepository";
const mockCreateServer = vi.mocked(createServer);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_SERVER_RESULT = {
  id: "server-uuid-new",
  name: "sandbox_writeonly",
  transport: "http" as const,
  endpoint: "http://localhost:8080/mcp",
  status: "draft" as const,
  last_sync_at: null,
  created_by: "user-uuid",
  has_credential: false,
  auth_type: null as null,
};

const VALID_REQUEST = {
  name: "sandbox_writeonly",
  transport: "http" as const,
  endpoint: "http://localhost:8080/mcp",
  auth: { type: "none" as const, secret: null, refresh_token: null },
};

// ---------------------------------------------------------------------------
// Test harness — no fake timers (causes TanStack Query deadlocks)
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

describe("useCreateMcpServer", () => {
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("C01 — mutate happy (auth=none) → invalidates ['admin','mcp','servers'] on success", async () => {
    mockCreateServer.mockResolvedValueOnce({ ok: true, value: MOCK_SERVER_RESULT });

    const { queryClient, Wrapper } = makeWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(
      () => useCreateMcpServer(onAuthFailure),
      { wrapper: Wrapper },
    );

    await act(async () => {
      result.current.mutate(VALID_REQUEST);
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Verify invalidation was called with the servers query key
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["admin", "mcp", "servers"] }),
    );
    expect(result.current.data?.id).toBe("server-uuid-new");
    expect(result.current.data?.has_credential).toBe(false);
  });

  it("C02 — mutate 422 → throws McpValidationError with fieldErrors", async () => {
    const validationError = new McpValidationError({
      secret: "Field required",
      name: "Name too short",
    });
    mockCreateServer.mockResolvedValueOnce({ ok: false, error: validationError });

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(
      () => useCreateMcpServer(onAuthFailure),
      { wrapper: Wrapper },
    );

    await act(async () => {
      result.current.mutate(VALID_REQUEST);
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(McpValidationError);
    const err = result.current.error as McpValidationError;
    expect(err.code).toBe("MCP_VALIDATION_ERROR");
    expect(err.fieldErrors["secret"]).toBe("Field required");
    expect(err.fieldErrors["name"]).toBe("Name too short");
  });

  it("C03 — mutate 500 → throws McpServerError", async () => {
    mockCreateServer.mockResolvedValueOnce({
      ok: false,
      error: new McpServerError(500),
    });

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(
      () => useCreateMcpServer(onAuthFailure),
      { wrapper: Wrapper },
    );

    await act(async () => {
      result.current.mutate(VALID_REQUEST);
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(McpServerError);
    expect((result.current.error as McpServerError).status).toBe(500);
  });

  it("C04 — secret NEVER in data result (§D-T004-SECRET-NEVER-PERSISTED)", async () => {
    const serverWithApiKey = {
      ...MOCK_SERVER_RESULT,
      has_credential: true,
      auth_type: "api_key" as const,
    };
    mockCreateServer.mockResolvedValueOnce({ ok: true, value: serverWithApiKey });

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(
      () => useCreateMcpServer(onAuthFailure),
      { wrapper: Wrapper },
    );

    const requestWithSecret = {
      ...VALID_REQUEST,
      auth: { type: "api_key" as const, secret: "vt-sandbox-key", refresh_token: null },
    };

    await act(async () => {
      result.current.mutate(requestWithSecret);
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // The result data MUST NOT contain secret or refresh_token (plaintext)
    expect(result.current.data).not.toHaveProperty("secret");
    expect(result.current.data).not.toHaveProperty("refresh_token");
    // has_credential bool is safe to expose — it's a boolean flag, not the key
    expect(result.current.data?.has_credential).toBe(true);
  });
});

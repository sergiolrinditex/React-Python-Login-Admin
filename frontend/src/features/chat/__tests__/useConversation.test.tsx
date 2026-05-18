/**
 * Hilo People — useConversation hook tests (§D-T002-TESTS).
 *
 * Slice/Phase: P03-S02-T008 — ConversationPage re-implementation / Phase 3.
 *   Re-implemented from reference branch f7f5f33 (P03-S02-T002).
 *
 * Responsibility: Integration tests for useConversation hook.
 *   authFetch is mocked at the fetch boundary. Real TanStack Query client.
 *
 * Cases:
 *   T01 — happy path: returns ConversationDetail on 200
 *   T02 — 401 final: throws ChatAuthExpiredError
 *   T03 — 403: throws ChatForbiddenError
 *   T04 — 404: throws ChatNotFoundError
 *   T05 — network error: throws ChatNetworkError
 *   T06 — disabled when id is empty string
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useConversation } from "../presentation/useConversation";
import {
  ChatAuthExpiredError,
  ChatForbiddenError,
  ChatNotFoundError,
  ChatNetworkError,
} from "../data/errors";

// ---------------------------------------------------------------------------
// Mock authFetch
// ---------------------------------------------------------------------------

vi.mock("../../auth/data/httpClient", () => ({
  authFetch: vi.fn(),
}));

import { authFetch } from "../../auth/data/httpClient";
const mockAuthFetch = vi.mocked(authFetch);

// ---------------------------------------------------------------------------
// Test wrapper with fresh QueryClient
// ---------------------------------------------------------------------------

function makeWrapper(): ({ children }: { children: ReactNode }) => ReactNode {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }): ReactNode {
    return (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );
  };
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_DETAIL = {
  id: "conv-aaa",
  user_id: "user-bbb",
  title: "Test conversation",
  language: "es" as const,
  created_at: "2026-05-14T10:00:00Z",
  updated_at: "2026-05-14T10:00:00Z",
  messages: [
    {
      id: "msg-1",
      conversation_id: "conv-aaa",
      role: "user" as const,
      content: "Hola",
      token_count: null,
      created_at: "2026-05-14T10:00:00Z",
    },
  ],
  citations: [],
};

function makeResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      "x-request-id": "test-r1",
    },
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useConversation", () => {
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("T01 — happy path: returns ConversationDetail on 200", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, { data: MOCK_DETAIL, meta: { request_id: "r1" }, errors: [] }),
    );

    const { result } = renderHook(
      () => useConversation("conv-aaa", onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toBeDefined();
    expect(result.current.data?.id).toBe("conv-aaa");
    expect(result.current.data?.messages).toHaveLength(1);
    expect(result.current.error).toBeNull();
  });

  it("T02 — 401 final: throws ChatAuthExpiredError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(401, { errors: [{ code: "AUTH_SESSION_EXPIRED" }] }),
    );

    const { result } = renderHook(
      () => useConversation("conv-aaa", onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.status).toBe("error"));

    expect(result.current.error).toBeInstanceOf(ChatAuthExpiredError);
  });

  it("T03 — 403: throws ChatForbiddenError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(403, { errors: [{ code: "CHAT_CONVERSATION_FORBIDDEN" }] }),
    );

    const { result } = renderHook(
      () => useConversation("conv-aaa", onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.status).toBe("error"));

    expect(result.current.error).toBeInstanceOf(ChatForbiddenError);
  });

  it("T04 — 404: throws ChatNotFoundError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(404, { errors: [{ code: "CHAT_CONVERSATION_NOT_FOUND" }] }),
    );

    const { result } = renderHook(
      () => useConversation("conv-aaa", onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.status).toBe("error"));

    expect(result.current.error).toBeInstanceOf(ChatNotFoundError);
  });

  it("T05 — network error: throws ChatNetworkError", async () => {
    mockAuthFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const { result } = renderHook(
      () => useConversation("conv-aaa", onAuthFailure),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.status).toBe("error"));

    expect(result.current.error).toBeInstanceOf(ChatNetworkError);
  });

  it("T06 — disabled when id is empty string", () => {
    const { result } = renderHook(
      () => useConversation("", onAuthFailure),
      { wrapper: makeWrapper() },
    );

    // With enabled=false, status remains 'pending' but no fetch fires
    expect(result.current.status).toBe("pending");
    expect(result.current.isLoading).toBe(false);
    expect(mockAuthFetch).not.toHaveBeenCalled();
  });
});

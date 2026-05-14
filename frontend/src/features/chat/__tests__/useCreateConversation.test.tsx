/**
 * Hilo People — useCreateConversation hook tests.
 *
 * Slice/Phase: P03-S02-T001 — ChatHomePage / Phase 3.
 *
 * Responsibility: Component-level tests for the useCreateConversation hook.
 *   Uses a real TanStack Query QueryClient test harness (per §10.1).
 *   chatRepository.createConversation is mocked at the module boundary.
 *
 * Cases:
 *   T01 — idle → pending → success lifecycle.
 *   T02 — onSuccess callback called with conversation data.
 *   T03 — onError callback called with typed ChatError.
 *   T04 — isPending true while mutation in-flight.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useCreateConversation } from "../presentation/useCreateConversation";
import { ChatNetworkError } from "../data/errors";

// ---------------------------------------------------------------------------
// Mock chatRepository
// ---------------------------------------------------------------------------

vi.mock("../data/chatRepository", () => ({
  createConversation: vi.fn(),
}));

import { createConversation } from "../data/chatRepository";
const mockCreateConversation = vi.mocked(createConversation);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_CONVERSATION = {
  conversation_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  title: "Test conversation",
  language: "es" as const,
  created_at: "2026-05-14T10:00:00Z",
};

// ---------------------------------------------------------------------------
// Test harness
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useCreateConversation", () => {
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("T01 — idle → pending → success lifecycle", async () => {
    mockCreateConversation.mockResolvedValueOnce({
      ok: true,
      value: MOCK_CONVERSATION,
    });

    const { result } = renderHook(
      () => useCreateConversation(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    expect(result.current.isPending).toBe(false);
    expect(result.current.data).toBeUndefined();

    act(() => {
      result.current.mutate({ initial_message: "hello", language: "es" });
    });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
      expect(result.current.data?.conversation_id).toBe(MOCK_CONVERSATION.conversation_id);
    });
  });

  it("T02 — onSuccess callback called with conversation data", async () => {
    mockCreateConversation.mockResolvedValueOnce({
      ok: true,
      value: MOCK_CONVERSATION,
    });

    const { result } = renderHook(
      () => useCreateConversation(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    const onSuccess = vi.fn();

    act(() => {
      result.current.mutate(
        { initial_message: "hello", language: "es" },
        { onSuccess },
      );
    });

    await waitFor(() => {
      // TanStack Query passes (data, variables, context) to onSuccess — check first arg
      expect(onSuccess).toHaveBeenCalledTimes(1);
      expect(onSuccess.mock.calls[0][0]).toEqual(MOCK_CONVERSATION);
    });
  });

  it("T03 — onError callback called with typed ChatError", async () => {
    const networkError = new ChatNetworkError("Fetch failed");
    mockCreateConversation.mockResolvedValueOnce({
      ok: false,
      error: networkError,
    });

    const { result } = renderHook(
      () => useCreateConversation(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    const onError = vi.fn();

    act(() => {
      result.current.mutate(
        { initial_message: "hello", language: "es" },
        { onError },
      );
    });

    await waitFor(() => {
      // TanStack Query passes (error, variables, context) to onError — check first arg
      expect(onError).toHaveBeenCalledTimes(1);
      expect(onError.mock.calls[0][0]).toBeInstanceOf(ChatNetworkError);
    });
  });

  it("T04 — error state set after failed mutation", async () => {
    const networkError = new ChatNetworkError("Network down");
    mockCreateConversation.mockResolvedValueOnce({
      ok: false,
      error: networkError,
    });

    const { result } = renderHook(
      () => useCreateConversation(onAuthFailure),
      { wrapper: makeWrapper() },
    );

    act(() => {
      result.current.mutate({ initial_message: "hello", language: "es" });
    });

    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(ChatNetworkError);
    });
  });
});

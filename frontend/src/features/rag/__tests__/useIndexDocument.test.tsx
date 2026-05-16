/**
 * Hilo People — useIndexDocument mutation hook tests.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: Tests for the useIndexDocument useMutation hook.
 *   ragRepository is mocked at module level.
 *
 * Cases:
 *   I01 — 202 success: mutation resolves with kind:'enqueued'.
 *   I02 — 409 in-progress: throws RagIndexInProgressError.
 *   I03 — 404 missing: throws RagDocumentNotFoundError.
 *   I04 — network error: throws RagNetworkError.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useIndexDocument } from "../presentation/useIndexDocument";
import {
  RagIndexInProgressError,
  RagDocumentNotFoundError,
  RagNetworkError,
} from "../data/errors";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../auth/presentation/AuthProvider", () => ({
  useAuth: vi.fn(() => ({ logout: vi.fn() })),
}));

vi.mock("../data/ragRepository", () => ({
  ragRepository: {
    listDocuments: vi.fn(),
    uploadDocument: vi.fn(),
    indexDocument: vi.fn(),
    listCollections: vi.fn(),
  },
}));

import { ragRepository } from "../data/ragRepository";
const mockIndexDocument = vi.mocked(ragRepository.indexDocument);

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useIndexDocument", () => {
  beforeEach(() => vi.clearAllMocks());

  it("I01 — 202 success: mutation resolves with kind:'enqueued'", async () => {
    mockIndexDocument.mockResolvedValueOnce({
      ok: true,
      value: { kind: "enqueued", job_id: "job-001", status: "pending" },
    });

    const { result } = renderHook(() => useIndexDocument(), { wrapper: makeWrapper() });

    act(() => {
      result.current.mutate("doc-001");
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.kind).toBe("enqueued");
    expect(result.current.data?.job_id).toBe("job-001");
  });

  it("I02 — 409 in-progress: throws RagIndexInProgressError", async () => {
    mockIndexDocument.mockResolvedValueOnce({
      ok: false,
      error: new RagIndexInProgressError("job-existing", "processing"),
    });

    const { result } = renderHook(() => useIndexDocument(), { wrapper: makeWrapper() });

    act(() => {
      result.current.mutate("doc-001");
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(RagIndexInProgressError);
    expect((result.current.error as RagIndexInProgressError).job_id).toBe("job-existing");
  });

  it("I03 — 404 missing: throws RagDocumentNotFoundError", async () => {
    mockIndexDocument.mockResolvedValueOnce({
      ok: false,
      error: new RagDocumentNotFoundError(),
    });

    const { result } = renderHook(() => useIndexDocument(), { wrapper: makeWrapper() });

    act(() => {
      result.current.mutate("nonexistent");
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(RagDocumentNotFoundError);
  });

  it("I04 — network error: throws RagNetworkError", async () => {
    mockIndexDocument.mockResolvedValueOnce({
      ok: false,
      error: new RagNetworkError("Network down"),
    });

    const { result } = renderHook(() => useIndexDocument(), { wrapper: makeWrapper() });

    act(() => {
      result.current.mutate("doc-001");
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(RagNetworkError);
  });
});

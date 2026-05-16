/**
 * Hilo People — useUploadDocument mutation hook tests.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: Tests for the useUploadDocument useMutation hook.
 *   ragRepository is mocked at module level.
 *
 * Cases:
 *   U01 — success 201 created path: mutation resolves with kind:'created'.
 *   U02 — success 200 dedup path: mutation resolves with kind:'dedup'.
 *   U03 — validation error 422: throws RagDocumentInvalidError.
 *   U04 — too large 413: throws RagDocumentTooLargeError.
 *   U05 — network error: throws RagNetworkError.
 *   U06 — on success: invalidates ["rag","documents"] query.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useUploadDocument } from "../presentation/useUploadDocument";
import {
  RagDocumentInvalidError,
  RagDocumentTooLargeError,
  RagNetworkError,
} from "../data/errors";
import type { RagDocument } from "../domain/types";

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
const mockUploadDocument = vi.mocked(ragRepository.uploadDocument);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_DOC: RagDocument = {
  id: "doc-001",
  collection_id: "coll-001",
  title: "Política Vacaciones",
  language: "es",
  source_uri: "s3://bucket/doc-001.pdf",
  status: "uploaded",
  uploaded_by: null,
  created_at: "2026-05-16T10:00:00Z",
};

const MOCK_FILE = new File(["pdf content"], "policy.pdf", { type: "application/pdf" });
const MOCK_REQUEST = {
  file: MOCK_FILE,
  title: "Política Vacaciones",
  language: "es" as const,
  collection_id: "coll-001",
};

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return {
    wrapper: ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children),
    queryClient,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useUploadDocument", () => {
  beforeEach(() => vi.clearAllMocks());

  it("U01 — success 201 created: mutation resolves with kind:'created'", async () => {
    mockUploadDocument.mockResolvedValueOnce({
      ok: true,
      value: { kind: "created", document: MOCK_DOC },
    });

    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useUploadDocument(), { wrapper });

    act(() => {
      result.current.mutate(MOCK_REQUEST);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.kind).toBe("created");
    expect(result.current.data?.document.id).toBe("doc-001");
  });

  it("U02 — success 200 dedup: mutation resolves with kind:'dedup'", async () => {
    mockUploadDocument.mockResolvedValueOnce({
      ok: true,
      value: { kind: "dedup", document: MOCK_DOC },
    });

    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useUploadDocument(), { wrapper });

    act(() => {
      result.current.mutate(MOCK_REQUEST);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.kind).toBe("dedup");
  });

  it("U03 — validation error 422: throws RagDocumentInvalidError", async () => {
    mockUploadDocument.mockResolvedValueOnce({
      ok: false,
      error: new RagDocumentInvalidError("Validation failed.", "collection_id"),
    });

    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useUploadDocument(), { wrapper });

    act(() => {
      result.current.mutate(MOCK_REQUEST);
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(RagDocumentInvalidError);
  });

  it("U04 — too large 413: throws RagDocumentTooLargeError", async () => {
    mockUploadDocument.mockResolvedValueOnce({
      ok: false,
      error: new RagDocumentTooLargeError(),
    });

    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useUploadDocument(), { wrapper });

    act(() => {
      result.current.mutate(MOCK_REQUEST);
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(RagDocumentTooLargeError);
  });

  it("U05 — network error: throws RagNetworkError", async () => {
    mockUploadDocument.mockResolvedValueOnce({
      ok: false,
      error: new RagNetworkError("Network down"),
    });

    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useUploadDocument(), { wrapper });

    act(() => {
      result.current.mutate(MOCK_REQUEST);
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(RagNetworkError);
  });

  it("U06 — on success: invalidates ['rag','documents'] query", async () => {
    mockUploadDocument.mockResolvedValueOnce({
      ok: true,
      value: { kind: "created", document: MOCK_DOC },
    });

    const { wrapper, queryClient } = makeWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUploadDocument(), { wrapper });

    act(() => {
      result.current.mutate(MOCK_REQUEST);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["rag", "documents"] }),
    );
  });
});

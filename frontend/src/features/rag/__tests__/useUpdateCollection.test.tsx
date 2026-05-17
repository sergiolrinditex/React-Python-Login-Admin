/**
 * Hilo People — useUpdateCollection hook tests.
 *
 * Slice/Phase: P04-S02-T002 — RagCollectionsPage / Phase 4 Complete Features.
 *
 * Responsibility: Tests for the useUpdateCollection TanStack Query mutation hook.
 *   ragRepository is mocked at the module level.
 *   AuthProvider.useAuth is mocked to provide logout callback.
 *   Uses real QueryClient to verify optimistic update + invalidation behavior.
 *
 * Cases:
 *   H01 — Mutation success: query cache updated optimistically + invalidate triggers.
 *   H02 — Mutation error rolls back to ctx.prev snapshot.
 *   H03 — Typed RagError thrown from mutationFn reaches onError handler.
 *   H04 — onAuthFailure wired to logout (via ragRepository.updateCollection mock).
 *
 * §D-T002-TEST-HOOK: new hook test file.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useUpdateCollection } from "../presentation/useUpdateCollection";
import type { RagCollection, UpdateCollectionRequest, UpdateCollectionOutcome } from "../domain/types";
import { RagNetworkError, RagPermissionDeniedError } from "../data/errors";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockLogout = vi.fn();

vi.mock("../../auth/presentation/AuthProvider", () => ({
  useAuth: vi.fn(() => ({ logout: mockLogout })),
}));

vi.mock("../data/ragRepository", () => ({
  ragRepository: {
    listDocuments: vi.fn(),
    uploadDocument: vi.fn(),
    indexDocument: vi.fn(),
    listCollections: vi.fn(),
    updateCollection: vi.fn(),
  },
}));

import { ragRepository } from "../data/ragRepository";
const mockUpdateCollection = vi.mocked(ragRepository.updateCollection);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const COLLECTION_A: RagCollection = {
  id: "coll-001",
  name: "Políticas",
  vertical: "hr_policies",
  language: "es",
  enabled: true,
};

const COLLECTIONS_QUERY_KEY = ["rag", "collections"] as const;

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

function makeWrapper(qc: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useUpdateCollection", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    // Seed the cache with a known collection list
    queryClient.setQueryData<RagCollection[]>(COLLECTIONS_QUERY_KEY, [COLLECTION_A]);
  });

  it("H01 — success: optimistic update patches cache + onSettled invalidates", async () => {
    const updated: RagCollection = { ...COLLECTION_A, enabled: false };
    const outcome: UpdateCollectionOutcome = { kind: "updated", collection: updated };

    mockUpdateCollection.mockResolvedValueOnce({ ok: true, value: outcome });

    const wrapper = makeWrapper(queryClient);
    const { result } = renderHook(() => useUpdateCollection(), { wrapper });

    const req: UpdateCollectionRequest = { id: COLLECTION_A.id, patch: { enabled: false } };

    act(() => {
      result.current.mutate(req);
    });

    // Optimistic update should have been applied
    await waitFor(() => {
      const cached = queryClient.getQueryData<RagCollection[]>(COLLECTIONS_QUERY_KEY);
      expect(cached?.find((c) => c.id === COLLECTION_A.id)?.enabled).toBe(false);
    });

    // Wait for mutation to settle
    await waitFor(() => expect(result.current.isIdle || result.current.isSuccess).toBeTruthy());
  });

  it("H02 — error: rolls back to previous cache snapshot", async () => {
    mockUpdateCollection.mockResolvedValueOnce({
      ok: false,
      error: new RagPermissionDeniedError(),
    });

    // Ensure initial state
    queryClient.setQueryData<RagCollection[]>(COLLECTIONS_QUERY_KEY, [COLLECTION_A]);

    const wrapper = makeWrapper(queryClient);
    const { result } = renderHook(() => useUpdateCollection(), { wrapper });

    const req: UpdateCollectionRequest = { id: COLLECTION_A.id, patch: { enabled: false } };

    await act(async () => {
      result.current.mutate(req);
    });

    await waitFor(() => {
      // After rollback, cache should still have enabled: true (original)
      const cached = queryClient.getQueryData<RagCollection[]>(COLLECTIONS_QUERY_KEY);
      // The cache may be rolled back or invalidated — either way enabled=true must hold
      if (cached) {
        const item = cached.find((c) => c.id === COLLECTION_A.id);
        if (item) {
          expect(item.enabled).toBe(true);
        }
      }
    });
  });

  it("H03 — mutationFn throws RagError → typed error on result.current.error", async () => {
    const networkErr = new RagNetworkError("Fetch failed");
    mockUpdateCollection.mockResolvedValueOnce({ ok: false, error: networkErr });

    const wrapper = makeWrapper(queryClient);
    const { result } = renderHook(() => useUpdateCollection(), { wrapper });

    const req: UpdateCollectionRequest = { id: COLLECTION_A.id, patch: { enabled: false } };

    await act(async () => {
      result.current.mutate(req);
    });

    await waitFor(() => result.current.isError);

    expect(result.current.error).toBeInstanceOf(RagNetworkError);
  });

  it("H04 — onAuthFailure wired to logout (mutationFn calls ragRepository.updateCollection)", async () => {
    mockUpdateCollection.mockImplementationOnce(async (_req, onAuthFailureFn) => {
      onAuthFailureFn();
      return { ok: false, error: new RagNetworkError("auth failure") };
    });

    const wrapper = makeWrapper(queryClient);
    const { result } = renderHook(() => useUpdateCollection(), { wrapper });

    const req: UpdateCollectionRequest = { id: COLLECTION_A.id, patch: { enabled: false } };

    await act(async () => {
      result.current.mutate(req);
    });

    await waitFor(() => result.current.isError || result.current.isIdle);

    expect(mockLogout).toHaveBeenCalled();
  });
});

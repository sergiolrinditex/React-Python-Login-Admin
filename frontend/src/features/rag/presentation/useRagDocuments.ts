/**
 * Hilo People — useRagDocuments hook.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: TanStack Query v5 useQuery wrapper for GET /admin/rag/documents.
 *   Returns the document list with auto-polling when any row is in a non-terminal state.
 *
 * §D-RAGDOC-POLLING-GATED: refetchInterval is 3s when any row is
 *   in {uploaded, pending, processing}; false otherwise. This prevents unnecessary
 *   polling when all documents are in a terminal state (indexed | failed).
 *
 * Key deps: TanStack Query v5, ragRepository, useAuth (for session expiry callback).
 */

import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { ragRepository } from "../data/ragRepository";
import { INFLIGHT_STATUSES, type RagDocument } from "../domain/types";
import type { ListDocumentsResponse } from "../domain/types";
import type { RagError } from "../data/errors";
import { useAuth } from "../../auth/presentation/AuthProvider";
import { logVerbose } from "../data/logger";

/** Query params passed to the hook. */
export interface UseRagDocumentsParams {
  collection_id?: string;
  status?: string;
  limit?: number;
}

/** Return type of useRagDocuments. */
export type UseRagDocumentsResult = UseQueryResult<ListDocumentsResponse, RagError>;

/**
 * Returns true when any document row is in a non-terminal index state.
 * Used to gate the refetchInterval.
 *
 * @param data - Current query data.
 */
function hasInflightDocuments(data: ListDocumentsResponse | undefined): boolean {
  if (!data) return false;
  return data.data.some((doc: RagDocument) =>
    INFLIGHT_STATUSES.includes(doc.status),
  );
}

/**
 * Hook: list RAG documents with optional filters.
 *
 * - Polls every 3s when any row is in a non-terminal state.
 * - Stops polling when all rows are indexed or failed.
 * - staleTime: 30s; gcTime: 5min (per project TanStack conventions).
 * - Aborts on unmount via TanStack's built-in signal handling.
 *
 * @param params - Optional filters (collection_id, status, limit).
 * @returns TanStack QueryResult<ListDocumentsResponse, RagError>.
 */
export function useRagDocuments(params: UseRagDocumentsParams = {}): UseRagDocumentsResult {
  const { logout } = useAuth();

  logVerbose("rag.hook.useRagDocuments.init", {
    collection_id: params.collection_id ?? null,
    status: params.status ?? null,
  });

  return useQuery<ListDocumentsResponse, RagError>({
    queryKey: ["rag", "documents", params],
    queryFn: async ({ signal }) => {
      logVerbose("rag.hook.useRagDocuments.fetch", { params });

      const result = await ragRepository.listDocuments(
        {
          collection_id: params.collection_id,
          limit: params.limit ?? 50,
          signal,
        },
        logout,
      );

      if (!result.ok) {
        logVerbose("rag.hook.useRagDocuments.error", { error: result.error.code });
        throw result.error;
      }

      logVerbose("rag.hook.useRagDocuments.ok", { count: result.value.data.length });
      return result.value;
    },
    staleTime: 30_000,
    gcTime: 300_000,
    // §D-RAGDOC-POLLING-GATED: poll only when inflight docs exist
    refetchInterval: (query) => (hasInflightDocuments(query.state.data) ? 3_000 : false),
    retry: false,
  });
}

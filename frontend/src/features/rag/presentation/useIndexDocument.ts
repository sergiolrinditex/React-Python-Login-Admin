/**
 * Hilo People — useIndexDocument mutation hook.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: TanStack Query v5 useMutation wrapper for
 *   POST /admin/rag/documents/{id}/index.
 *   On success → patches the row's status to "processing" via setQueryData
 *   so the list immediately shows the indexing state without waiting for a refetch.
 *   Also invalidates to trigger the polling refetchInterval.
 *
 * Key deps: TanStack Query v5, ragRepository, useAuth.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { UseMutationResult } from "@tanstack/react-query";
import { ragRepository } from "../data/ragRepository";
import type { IndexDocumentOutcome, ListDocumentsResponse } from "../domain/types";
import type { RagError } from "../data/errors";
import { useAuth } from "../../auth/presentation/AuthProvider";
import { logVerbose, logWarn, logError } from "../data/logger";

/** Return type of useIndexDocument. */
export type UseIndexDocumentResult = UseMutationResult<
  IndexDocumentOutcome,
  RagError,
  string
>;

/**
 * Hook: enqueue vectorization for a RAG document.
 *
 * On success:
 *   1. Patches the target document's status to "processing" in the cache.
 *   2. Invalidates ["rag","documents"] to restart polling refetchInterval.
 *
 * On 409 in_progress: the error is RagIndexInProgressError (surfaced in UI).
 *
 * @returns TanStack MutationResult<IndexDocumentOutcome, RagError, string>.
 */
export function useIndexDocument(): UseIndexDocumentResult {
  const queryClient = useQueryClient();
  const { logout } = useAuth();

  return useMutation<IndexDocumentOutcome, RagError, string>({
    mutationFn: async (documentId: string) => {
      logVerbose("rag.hook.useIndexDocument.start", { doc_id: documentId });

      const result = await ragRepository.indexDocument(documentId, { onAuthFailure: logout });

      if (!result.ok) {
        logWarn("rag.hook.useIndexDocument.error", {
          doc_id: documentId,
          error: result.error.code,
        });
        throw result.error;
      }

      logVerbose("rag.hook.useIndexDocument.ok", {
        doc_id: documentId,
        kind: result.value.kind,
        job_id: result.value.job_id,
      });

      return result.value;
    },
    onSuccess: async (_data, documentId) => {
      logVerbose("rag.hook.useIndexDocument.patch_cache", { doc_id: documentId });

      // Patch the document status immediately so the UI shows the transition.
      queryClient.setQueriesData<ListDocumentsResponse>(
        { queryKey: ["rag", "documents"] },
        (old) => {
          if (!old) return old;
          return {
            ...old,
            data: old.data.map((doc) =>
              doc.id === documentId ? { ...doc, status: "processing" as const } : doc,
            ),
          };
        },
      );

      // Invalidate to restart refetchInterval polling.
      await queryClient.invalidateQueries({ queryKey: ["rag", "documents"] });
    },
    onError: (error, documentId) => {
      logError("rag.hook.useIndexDocument.mutation_error", {
        doc_id: documentId,
        error: error.code,
      });
    },
  });
}

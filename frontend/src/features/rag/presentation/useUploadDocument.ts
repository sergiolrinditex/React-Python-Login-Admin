/**
 * Hilo People — useUploadDocument mutation hook.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: TanStack Query v5 useMutation wrapper for POST /admin/rag/documents.
 *   On success → invalidates ["rag","documents"] to refresh the list.
 *   Exposes mutate/mutateAsync, isPending, isError, error, data.
 *
 * Key deps: TanStack Query v5, ragRepository, useAuth (session expiry callback).
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { UseMutationResult } from "@tanstack/react-query";
import { ragRepository } from "../data/ragRepository";
import type { UploadDocumentRequest, UploadDocumentOutcome } from "../domain/types";
import type { RagError } from "../data/errors";
import { useAuth } from "../../auth/presentation/AuthProvider";
import { logVerbose, logError } from "../data/logger";

/** Return type of useUploadDocument. */
export type UseUploadDocumentResult = UseMutationResult<
  UploadDocumentOutcome,
  RagError,
  UploadDocumentRequest
>;

/**
 * Hook: upload a RAG document via multipart/form-data.
 *
 * On success: invalidates ["rag","documents"] so the list refreshes.
 * On error: error is a typed RagError.
 *
 * §D-RAGDOC-AUTHFETCH-FORMDATA: FormData is passed directly; Content-Type is NOT set.
 *
 * @returns TanStack MutationResult<UploadDocumentOutcome, RagError, UploadDocumentRequest>.
 */
export function useUploadDocument(): UseUploadDocumentResult {
  const queryClient = useQueryClient();
  const { logout } = useAuth();

  return useMutation<UploadDocumentOutcome, RagError, UploadDocumentRequest>({
    mutationFn: async (request: UploadDocumentRequest) => {
      logVerbose("rag.hook.useUploadDocument.start", {
        mime_type: request.file.type,
        language: request.language,
        collection_id: request.collection_id,
      });

      const result = await ragRepository.uploadDocument(request, { onAuthFailure: logout });

      if (!result.ok) {
        logError("rag.hook.useUploadDocument.error", { error: result.error.code });
        throw result.error;
      }

      logVerbose("rag.hook.useUploadDocument.ok", {
        kind: result.value.kind,
        doc_id: result.value.document.id,
      });

      return result.value;
    },
    onSuccess: async (data) => {
      logVerbose("rag.hook.useUploadDocument.success_invalidate", {
        kind: data.kind,
        doc_id: data.document.id,
      });
      await queryClient.invalidateQueries({ queryKey: ["rag", "documents"] });
    },
    onError: (error) => {
      logError("rag.hook.useUploadDocument.mutation_error", { error: error.code });
    },
  });
}

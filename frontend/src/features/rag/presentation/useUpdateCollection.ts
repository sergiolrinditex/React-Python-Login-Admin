/**
 * Hilo People — useUpdateCollection mutation hook.
 *
 * Slice/Phase: P04-S02-T002 — RagCollectionsPage / Phase 4 Complete Features.
 *
 * Responsibility: TanStack Query v5 useMutation wrapper for
 *   PATCH /api/v1/admin/rag/collections/{id}.
 *   Implements optimistic update (§D-T002-OPTIMISTIC-PATCH):
 *     1. cancelQueries for ["rag","collections"]
 *     2. setQueryData with merged patch (optimistic)
 *     3. onError: revert to ctx.prev snapshot
 *     4. onSettled: invalidate ["rag","collections"] (authoritative server re-fetch)
 *
 * §D-T002-HOOK: new file, sibling to existing presentation hooks.
 * §D-T002-LOGS-PII-CLEAN: logs collection_id and field keys only, never values.
 *
 * Key deps: TanStack Query v5, ragRepository singleton, useAuth logout.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { UseMutationResult } from "@tanstack/react-query";
import { ragRepository } from "../data/ragRepository";
import type { RagCollection, UpdateCollectionRequest, UpdateCollectionOutcome } from "../domain/types";
import type { RagError } from "../data/errors";
import { useAuth } from "../../auth/presentation/AuthProvider";
import { logVerbose, logError } from "../data/logger";

/** Canonical query key for RAG collections — must match useRagCollections. */
const COLLECTIONS_QUERY_KEY = ["rag", "collections"] as const;

/** Context stored between onMutate → onError for optimistic rollback. */
interface MutationContext {
  prev: RagCollection[] | undefined;
}

/**
 * Hook: PATCH a RAG collection's editable fields.
 *
 * Applies an optimistic cache update on mutation start.
 * Reverts to the previous snapshot on error.
 * Invalidates the collection query on settle (re-fetches from server).
 *
 * @returns TanStack UseMutationResult<UpdateCollectionOutcome, RagError, UpdateCollectionRequest>.
 */
export function useUpdateCollection(): UseMutationResult<
  UpdateCollectionOutcome,
  RagError,
  UpdateCollectionRequest,
  MutationContext
> {
  const { logout } = useAuth();
  const queryClient = useQueryClient();

  return useMutation<UpdateCollectionOutcome, RagError, UpdateCollectionRequest, MutationContext>({
    mutationKey: ["rag", "collections", "update"],

    mutationFn: async (req: UpdateCollectionRequest): Promise<UpdateCollectionOutcome> => {
      const result = await ragRepository.updateCollection(req, logout);
      if (!result.ok) throw result.error;
      return result.value;
    },

    /**
     * Optimistic update: cancel in-flight queries, snapshot prev, apply patch.
     * §D-T002-OPTIMISTIC-PATCH: cancelQueries + setQueryData with merged patch.
     */
    onMutate: async (req: UpdateCollectionRequest): Promise<MutationContext> => {
      logVerbose("rag.hook.useUpdateCollection.onMutate", {
        collection_id: req.id,
        fields: Object.keys(req.patch),
      });

      // Cancel any outgoing re-fetches so they don't overwrite optimistic update.
      await queryClient.cancelQueries({ queryKey: COLLECTIONS_QUERY_KEY });

      // Snapshot current data for rollback.
      const prev = queryClient.getQueryData<RagCollection[]>(COLLECTIONS_QUERY_KEY);

      // Apply optimistic patch immediately.
      queryClient.setQueryData<RagCollection[]>(COLLECTIONS_QUERY_KEY, (old) =>
        old?.map((c) => (c.id === req.id ? { ...c, ...req.patch } : c)),
      );

      return { prev };
    },

    /**
     * Rollback: restore previous snapshot on error.
     */
    onError: (err: RagError, _req: UpdateCollectionRequest, ctx?: MutationContext): void => {
      logError("rag.hook.useUpdateCollection.onError", { error: err.code });
      if (ctx?.prev !== undefined) {
        queryClient.setQueryData<RagCollection[]>(COLLECTIONS_QUERY_KEY, ctx.prev);
      }
    },

    /**
     * After success: log the outcome.
     */
    onSuccess: (data: UpdateCollectionOutcome): void => {
      logVerbose("rag.hook.useUpdateCollection.onSuccess", {
        collection_id: data.collection.id,
      });
    },

    /**
     * Always invalidate to sync with server state (success or error).
     * §D-T002-OPTIMISTIC-PATCH: single source of truth via server re-fetch.
     */
    onSettled: (): void => {
      void queryClient.invalidateQueries({ queryKey: COLLECTIONS_QUERY_KEY });
    },
  });
}

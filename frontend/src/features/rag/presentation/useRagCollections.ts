/**
 * Hilo People — useRagCollections hook.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: TanStack Query v5 useQuery wrapper for GET /admin/rag/collections.
 *   Provides the collection list for the upload form dropdown.
 *   Collections change rarely → staleTime 60s.
 *
 * Key deps: TanStack Query v5, ragRepository, useAuth (session expiry callback).
 */

import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { ragRepository } from "../data/ragRepository";
import type { RagCollection } from "../domain/types";
import type { RagError } from "../data/errors";
import { useAuth } from "../../auth/presentation/AuthProvider";
import { logVerbose } from "../data/logger";

/** Return type of useRagCollections. */
export type UseRagCollectionsResult = UseQueryResult<RagCollection[], RagError>;

/**
 * Hook: list active RAG collections for the upload form dropdown.
 *
 * - staleTime: 60s (collections rarely change).
 * - gcTime: 5min.
 * - Aborts on unmount via TanStack signal.
 *
 * @returns TanStack QueryResult<RagCollection[], RagError>.
 */
export function useRagCollections(): UseRagCollectionsResult {
  const { logout } = useAuth();

  logVerbose("rag.hook.useRagCollections.init");

  return useQuery<RagCollection[], RagError>({
    queryKey: ["rag", "collections"],
    queryFn: async ({ signal }) => {
      logVerbose("rag.hook.useRagCollections.fetch");

      const result = await ragRepository.listCollections({ signal, onAuthFailure: logout });

      if (!result.ok) {
        logVerbose("rag.hook.useRagCollections.error", { error: result.error.code });
        throw result.error;
      }

      logVerbose("rag.hook.useRagCollections.ok", { count: result.value.length });
      return result.value;
    },
    staleTime: 60_000,
    gcTime: 300_000,
    retry: false,
  });
}

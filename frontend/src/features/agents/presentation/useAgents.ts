/**
 * Hilo People — useAgents hook.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: TanStack Query v5 useQuery wrapper around agentsRepository.listAgents.
 *   Returns the list of AI agents for the authenticated admin.
 *
 * §D-T005-USEAGENTS (P04-S02-T005 task pack §8.2)
 *
 * Clean Architecture: presentation/ layer — depends on data/agentsRepository.
 *   AgentsPage depends on this hook; no direct repository imports in the page.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR via logVerbose/logWarn.
 * Logging: PII-clean — no agent names, no tool values, only count.
 *
 * Key deps: @tanstack/react-query v5 (useQuery), agentsRepository.listAgents.
 */

import { useQuery } from "@tanstack/react-query";
import type { Agent } from "../domain/types";
import type { AgentsError } from "../data/errors";
import { listAgents } from "../data/agentsRepository";
import { logVerbose, logWarn } from "../data/logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const AGENTS_QUERY_KEY = ["admin", "agents"] as const;
const STALE_TIME = 30_000;      // 30 seconds
const GC_TIME = 5 * 60_000;    // 5 minutes

// ---------------------------------------------------------------------------
// Public hook
// ---------------------------------------------------------------------------

/**
 * Fetches the list of AI agents for the admin panel.
 *
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns TanStack useQuery result with Agent[] as data type.
 */
export function useAgents(onAuthFailure: () => void) {
  return useQuery<Agent[], AgentsError>({
    queryKey: AGENTS_QUERY_KEY,
    queryFn: async () => {
      logVerbose("agents.useAgents.fetch.start");

      const result = await listAgents(onAuthFailure);

      if (!result.ok) {
        logWarn("agents.useAgents.fetch.error", { code: result.error.code });
        throw result.error;
      }

      logVerbose("agents.useAgents.fetch.success", {
        count: result.value.length,
      });

      return result.value;
    },
    staleTime: STALE_TIME,
    gcTime: GC_TIME,
  });
}

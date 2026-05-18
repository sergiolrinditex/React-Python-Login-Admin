/**
 * Hilo People — useUpdateAgentTools hook.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: TanStack Query v5 useMutation wrapper for
 *   PATCH /api/v1/admin/ai/agents/{agentId}/tools.
 *
 * §D-T005-USEUPDATETOOLS (P04-S02-T005 task pack §8.2)
 * §D-T005-PER-ROW-MUTATION-STATE (P-43 #1): ONE shared useMutation instance.
 *   Per-row pending state derived via useMutationState with mutationKey filter.
 *   NEVER one useMutation per row (breaks rules-of-hooks if rows conditionally rendered).
 * §D-T005-OPTIMISTIC-TOOLS (P-44 #4): cancelQueries + setQueryData optimistic update.
 *   onMutate: snapshot + optimistic agent. onError: revert. onSettled: invalidate.
 *
 * Clean Architecture: presentation/ layer — depends on data/agentsRepository.
 *   AgentsPage depends on this hook; no direct repository imports in the page.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR via logVerbose/logWarn.
 *
 * Key deps: @tanstack/react-query v5 (useMutation, useQueryClient), agentsRepository.updateAgentTools.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Agent, UpdateAgentToolsRequest } from "../domain/types";
import type { AgentsError } from "../data/errors";
import { updateAgentTools } from "../data/agentsRepository";
import { logVerbose, logWarn } from "../data/logger";
import { AGENTS_QUERY_KEY } from "./useAgents";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UpdateAgentToolsVariables {
  /** UUID of the agent to update. */
  agentId: string;
  /** Request body with tool_ids array (set-replace). */
  request: UpdateAgentToolsRequest;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Shared mutation key base for agent tool updates.
 * §D-T005-PER-ROW-MUTATION-STATE: per-row pending state filtered from this key.
 */
export const UPDATE_AGENT_TOOLS_MUTATION_KEY = ["agents", "updateTools"] as const;

// ---------------------------------------------------------------------------
// Public hook
// ---------------------------------------------------------------------------

/**
 * Shared mutation hook for updating agent bound tools (set-replace).
 *
 * §D-T005-PER-ROW-MUTATION-STATE: use with useMutationState to derive per-row pending:
 *   useMutationState({ filters: { mutationKey: UPDATE_AGENT_TOOLS_MUTATION_KEY } })
 *
 * §D-T005-OPTIMISTIC-TOOLS: optimistic update on mutate, revert on error, invalidate on settled.
 *
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns TanStack useMutation result.
 */
export function useUpdateAgentTools(onAuthFailure: () => void) {
  const queryClient = useQueryClient();

  return useMutation<Agent, AgentsError, UpdateAgentToolsVariables>({
    mutationKey: UPDATE_AGENT_TOOLS_MUTATION_KEY,
    mutationFn: async ({ agentId, request }: UpdateAgentToolsVariables) => {
      // PII-CLEAN: log agent_id and count only — never tool_id values
      logVerbose("agents.useUpdateAgentTools.mutate.start", {
        agent_id: agentId,
        tool_count: request.tool_ids.length,
      });

      const result = await updateAgentTools(agentId, request, onAuthFailure);

      if (!result.ok) {
        logWarn("agents.useUpdateAgentTools.mutate.error", {
          agent_id: agentId,
          code: result.error.code,
        });
        throw result.error;
      }

      logVerbose("agents.useUpdateAgentTools.mutate.success", {
        agent_id: agentId,
        bound_tool_count: result.value.bound_tools.length,
      });

      return result.value;
    },

    // §D-T005-OPTIMISTIC-TOOLS: optimistic update on mutate
    onMutate: async ({ agentId, request }: UpdateAgentToolsVariables) => {
      // Cancel outgoing refetches so they don't overwrite the optimistic update
      await queryClient.cancelQueries({ queryKey: AGENTS_QUERY_KEY });

      // Snapshot previous value for rollback
      const snapshot = queryClient.getQueryData<Agent[]>(AGENTS_QUERY_KEY);

      // Optimistically update the agent in the cache
      queryClient.setQueryData<Agent[]>(AGENTS_QUERY_KEY, (prev) => {
        if (!prev) return prev;
        return prev.map((agent) => {
          if (agent.id !== agentId) return agent;
          // Optimistic: mark bound_tools as the tool_ids requested (minimal shape)
          const optimisticTools = request.tool_ids.map((id) => ({
            id,
            name: id,
            server_name: "",
            enabled: true,
            requires_approval: false,
            risk_level: "unknown",
          }));
          return { ...agent, bound_tools: optimisticTools };
        });
      });

      logVerbose("agents.useUpdateAgentTools.onMutate.optimistic", {
        agent_id: agentId,
        tool_count: request.tool_ids.length,
      });

      return { snapshot };
    },

    // Revert optimistic update on error
    onError: (err, { agentId }, context) => {
      const ctx = context as { snapshot?: Agent[] } | undefined;
      if (ctx?.snapshot !== undefined) {
        queryClient.setQueryData<Agent[]>(AGENTS_QUERY_KEY, ctx.snapshot);
      }
      logWarn("agents.useUpdateAgentTools.onError.reverted", {
        agent_id: agentId,
        error: (err as AgentsError).code,
      });
    },

    // Always invalidate to get authoritative data from server
    onSettled: () => {
      // §D-T005-OPTIMISTIC-TOOLS: invalidate to refresh after mutation settles
      void queryClient.invalidateQueries({ queryKey: AGENTS_QUERY_KEY });
    },
  });
}

/**
 * Hilo People — useStartAgentRun hook.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: TanStack Query v5 useMutation wrapper for POST /api/v1/agents/runs.
 *   Returns the shared mutation instance used for all per-agent run launchers.
 *   NO cache invalidation — agent_runs not surfaced as a list in v1.
 *
 * §D-T005-USESTARTRUN (P04-S02-T005 task pack §8.2)
 * §D-T005-502-INTENT: 502 mapped to AgentsRunUnreachableError — expected dev sandbox path.
 * §D-T005-BACKEND-NEW-409: 409 AGENT_DISABLED mapped to AgentsAgentDisabledError.
 *
 * Clean Architecture: presentation/ layer — depends on data/agentsRepository.
 *   AgentsPage depends on this hook; no direct repository imports in the page.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR via logVerbose/logWarn.
 * Logging: PII-CLEAN — never log run input text.
 *
 * Key deps: @tanstack/react-query v5 (useMutation), agentsRepository.startAgentRun.
 */

import { useMutation } from "@tanstack/react-query";
import type { StartAgentRunRequest, StartAgentRunResult } from "../domain/types";
import type { AgentsError } from "../data/errors";
import { startAgentRun } from "../data/agentsRepository";
import { logVerbose, logWarn } from "../data/logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Base mutation key for agent run start operations. */
export const START_AGENT_RUN_MUTATION_KEY = ["agents", "startRun"] as const;

// ---------------------------------------------------------------------------
// Public hook
// ---------------------------------------------------------------------------

/**
 * Shared mutation hook for starting an agent run.
 *
 * Page reads latest `data` from the mutation state to render outcome.
 * NO list query invalidation in v1 (agent_runs not fetched as a list).
 *
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns TanStack useMutation result.
 */
export function useStartAgentRun(onAuthFailure: () => void) {
  return useMutation<StartAgentRunResult, AgentsError, StartAgentRunRequest>({
    mutationKey: START_AGENT_RUN_MUTATION_KEY,
    mutationFn: async (request: StartAgentRunRequest) => {
      // PII-CLEAN: log agent_id only — never log input text
      logVerbose("agents.useStartAgentRun.mutate.start", {
        agent_id: request.agent_id,
      });

      const result = await startAgentRun(request, onAuthFailure);

      if (!result.ok) {
        logWarn("agents.useStartAgentRun.mutate.error", {
          agent_id: request.agent_id,
          code: result.error.code,
        });
        throw result.error;
      }

      logVerbose("agents.useStartAgentRun.mutate.success", {
        agent_id: request.agent_id,
        run_id: result.value.run_id,
        status: result.value.status,
      });

      return result.value;
    },
    // No onSuccess invalidation: agent_runs not a list in v1
  });
}

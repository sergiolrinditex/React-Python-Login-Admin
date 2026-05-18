/**
 * Hilo People — Agents feature repository port (interface).
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: Port (interface) for the agents data layer.
 *   Defines what operations the domain needs; the data layer implements them.
 *   No imports of external libs, no React, no fetch calls here.
 *
 * §D-T005-PORT (P04-S02-T005 task pack §8.1)
 *
 * Clean Architecture: presentation/ depends on this port, NOT on agentsRepository.ts
 *   directly. This decouples the UI from fetch implementation details.
 *
 * Wire contract source: TECHNICAL_GUIDE §6.1/§6.2/§6.3 of task pack.
 */

import type { Result } from "./types";
import type { Agent, UpdateAgentToolsRequest, StartAgentRunRequest, StartAgentRunResult } from "./types";
import type { AgentsError } from "../data/errors";

// ---------------------------------------------------------------------------
// Port interface
// ---------------------------------------------------------------------------

/**
 * Repository port for agents operations.
 *
 * All methods return Promise<Result<T, AgentsError>> — never throw to the caller.
 * §D-T005-PORT: port for the agents feature.
 */
export interface IAgentsRepository {
  /**
   * Lists all AI agents for the authenticated admin.
   *
   * @param onAuthFailure - Called when session expires and cannot be refreshed.
   * @returns Result<Agent[], AgentsError>
   */
  listAgents(onAuthFailure: () => void): Promise<Result<Agent[], AgentsError>>;

  /**
   * Updates the bound tools for a specific agent (set-replace).
   *
   * @param agentId - UUID of the agent to update.
   * @param request - Request body with tool_ids (set-replace).
   * @param onAuthFailure - Called when session expires and cannot be refreshed.
   * @returns Result<Agent, AgentsError> — full agent with refreshed bound_tools.
   */
  updateAgentTools(
    agentId: string,
    request: UpdateAgentToolsRequest,
    onAuthFailure: () => void,
  ): Promise<Result<Agent, AgentsError>>;

  /**
   * Starts a new agent run.
   *
   * @param request - Request body with agent_id and input.
   * @param onAuthFailure - Called when session expires and cannot be refreshed.
   * @returns Result<StartAgentRunResult, AgentsError>
   */
  startAgentRun(
    request: StartAgentRunRequest,
    onAuthFailure: () => void,
  ): Promise<Result<StartAgentRunResult, AgentsError>>;
}

/**
 * Hilo People — Agents feature barrel.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: Public surface for the agents feature module.
 *   Mirrors features/mcp/index.ts pattern (P-29 #barrel).
 *
 * §D-T005-BARREL (P04-S02-T005 task pack §8.1)
 *
 * Import from this barrel to keep page imports clean.
 * Do NOT import internal sub-paths from outside the feature.
 */

export type {
  Agent,
  BoundTool,
  AgentRun,
  AgentRunStatus,
  UpdateAgentToolsRequest,
  StartAgentRunRequest,
  StartAgentRunResult,
} from "./domain/types";
export type { AgentsError } from "./data/errors";
export {
  AgentsAuthExpiredError,
  AgentsForbiddenError,
  AgentsAgentNotFoundError,
  AgentsToolNotFoundError,
  AgentsToolNotApprovedError,
  AgentsAgentDisabledError,
  AgentsRunUnreachableError,
  AgentsRateLimitedError,
  AgentsServerError,
  AgentsNetworkError,
} from "./data/errors";
export { useAgents, AGENTS_QUERY_KEY } from "./presentation/useAgents";
export {
  useUpdateAgentTools,
  UPDATE_AGENT_TOOLS_MUTATION_KEY,
} from "./presentation/useUpdateAgentTools";
export {
  useStartAgentRun,
  START_AGENT_RUN_MUTATION_KEY,
} from "./presentation/useStartAgentRun";

/**
 * Hilo People — Agents feature domain types.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: Domain types for the AI agents feature.
 *   Mirrors backend schemas.py AgentOut + BoundToolOut + AgentRunCreatedOut exactly.
 *   No external imports — pure domain layer.
 *
 * §D-T005-DOMAIN (P04-S02-T005 task pack §8.1)
 *
 * Clean Architecture: domain layer — no React, no fetch, no external libs.
 *   Presentation and data layers import from here; domain imports nothing external.
 *
 * Wire contract source: TECHNICAL_GUIDE §6.1 + §6.2 + §6.3 of task pack.
 */

// Re-export Result type from auth domain for reuse (P-29 #2 pattern)
export type { Result } from "../../auth/domain/AuthRepository";

// ---------------------------------------------------------------------------
// AgentRunStatus literal union
// ---------------------------------------------------------------------------

/** Status of an agent run. Open union to tolerate future backend additions. */
export type AgentRunStatus =
  | "pending"
  | "running"
  | "done"
  | "failed"
  | "cancelled"
  | (string & {});

// ---------------------------------------------------------------------------
// BoundTool — mirrors backend BoundToolOut
// ---------------------------------------------------------------------------

/**
 * A tool bound to an agent.
 *
 * Returned as part of Agent.bound_tools array.
 * §D-T005-DOMAIN: approval state from mcp_tools.
 */
export interface BoundTool {
  /** UUID of the MCP tool. */
  id: string;
  /** Human-readable name of the tool. */
  name: string;
  /** Name of the MCP server providing this tool. */
  server_name: string;
  /** Whether the tool is approved (enabled=true in mcp_tools). */
  enabled: boolean;
  /** Whether this tool requires explicit approval before binding. */
  requires_approval: boolean;
  /** Risk level string: "low" | "medium" | "high" | arbitrary string. */
  risk_level: string;
}

// ---------------------------------------------------------------------------
// Agent — mirrors backend AgentOut
// ---------------------------------------------------------------------------

/**
 * AI agent entity as returned by GET /api/v1/admin/ai/agents.
 *
 * §D-T005-DOMAIN: mirrors AgentOut schema exactly.
 * Note: config (JSONB) is typed as Record<string,unknown> — MUST NOT be rendered
 * in v1 UI (R-6 PII risk). Page only shows name + description.
 */
export interface Agent {
  /** UUID of the agent record. */
  id: string;
  /** Human-readable name of the agent. */
  name: string;
  /** Optional description of the agent. */
  description: string | null;
  /** Whether the agent is enabled. Disabled agents return 409 on POST /runs. */
  enabled: boolean;
  /** JSONB config. Do NOT render in v1 UI — PII/security risk. */
  config: Record<string, unknown>;
  /** Approved tools bound to this agent. */
  bound_tools: BoundTool[];
}

// ---------------------------------------------------------------------------
// Request/response types for mutations
// ---------------------------------------------------------------------------

/**
 * Request body for PATCH /api/v1/admin/ai/agents/{id}/tools.
 * Set-replace semantics: empty array unbinds all tools.
 */
export interface UpdateAgentToolsRequest {
  /** Array of tool UUIDs to bind (set-replace). */
  tool_ids: string[];
}

/**
 * Request body for POST /api/v1/agents/runs.
 * §D-T005-DOMAIN: input 1..4000 chars validated both client-side and server-side.
 */
export interface StartAgentRunRequest {
  /** UUID of the agent to run. */
  agent_id: string;
  /** Input text for the agent. 1..4000 chars. */
  input: string;
}

/**
 * Response data from POST /api/v1/agents/runs.
 */
export interface StartAgentRunResult {
  /** UUID of the created agent run. */
  run_id: string;
  /** Initial status of the run. */
  status: AgentRunStatus;
}

// ---------------------------------------------------------------------------
// AgentRun — lightweight run entity (not fetched as a list in v1)
// ---------------------------------------------------------------------------

/**
 * An agent run entity (informational; not fetched as a list in v1).
 */
export interface AgentRun {
  run_id: string;
  status: AgentRunStatus;
}

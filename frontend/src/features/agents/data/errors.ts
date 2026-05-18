/**
 * Hilo People — Agents feature domain errors.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: Typed error classes for agents operations.
 *   agentsRepository.ts returns these via Result<T,E> patterns.
 *   Non-negotiables §error-handling: never catch generic Error — use typed domain errors.
 *
 * §D-T005-ERRORS (P04-S02-T005 task pack §8.1)
 *
 * Mirrors features/mcp/data/errors.ts pattern.
 * Source: TECHNICAL_GUIDE §6.1/§6.2/§6.3 + §D-T005-BACKEND-NEW-409 (task pack §8.6).
 */

// ---------------------------------------------------------------------------
// Agents error classes
// ---------------------------------------------------------------------------

/**
 * Session expired — server returned 401 after refresh exhausted.
 * authFetch single-flight exhausted; recovery is impossible without re-login.
 */
export class AgentsAuthExpiredError extends Error {
  public readonly code = "AGENTS_AUTH_EXPIRED";

  constructor(message = "Session expired. Please sign in again.") {
    super(message);
    this.name = "AgentsAuthExpiredError";
  }
}

/**
 * Forbidden — server returned 403 (role missing or insufficient).
 * Page-level: RequireRole catches this at routing. In-page 403 surfaces this.
 */
export class AgentsForbiddenError extends Error {
  public readonly code = "AGENTS_FORBIDDEN";

  constructor(message = "You do not have permission to perform this action.") {
    super(message);
    this.name = "AgentsForbiddenError";
  }
}

/**
 * Agent not found — server returned 404 for PATCH /tools or POST /runs.
 */
export class AgentsAgentNotFoundError extends Error {
  public readonly code = "AGENT_NOT_FOUND";

  constructor(message = "Agent not found.") {
    super(message);
    this.name = "AgentsAgentNotFoundError";
  }
}

/**
 * Tool not found — server returned 400 AGENT_TOOL_NOT_FOUND on PATCH /tools.
 * Carries offending tool_id from error message.
 */
export class AgentsToolNotFoundError extends Error {
  public readonly code = "AGENT_TOOL_NOT_FOUND";

  constructor(message = "One or more tools were not found.") {
    super(message);
    this.name = "AgentsToolNotFoundError";
  }
}

/**
 * Tool not approved — server returned 400 AGENT_TOOL_NOT_APPROVED on PATCH /tools.
 * Tool exists but enabled=false in mcp_tools.
 */
export class AgentsToolNotApprovedError extends Error {
  public readonly code = "AGENT_TOOL_NOT_APPROVED";

  constructor(message = "One or more tools are not approved.") {
    super(message);
    this.name = "AgentsToolNotApprovedError";
  }
}

/**
 * Agent disabled — server returned 409 AGENT_DISABLED on POST /runs.
 * §D-T005-BACKEND-NEW-409: not in TECHNICAL_GUIDE §6.2 but present in router_runs.py:104.
 * UI renders inline near run launcher as error_validation (not error_network).
 */
export class AgentsAgentDisabledError extends Error {
  public readonly code = "AGENT_DISABLED";

  constructor(message = "This agent is disabled.") {
    super(message);
    this.name = "AgentsAgentDisabledError";
  }
}

/**
 * Agent run failed / unreachable — server returned 502 on POST /runs.
 * Maps to AgentsRunUnreachableError — analogous to McpServerUnreachableError.
 * §D-T005-502-INTENT: expected evidence in dev sandbox (DeepAgents/LangGraph down).
 * Maps to i18n key errors:AGENT_RUN_FAILED.
 */
export class AgentsRunUnreachableError extends Error {
  public readonly code = "AGENT_RUN_FAILED";

  constructor(message = "Agent run failed — downstream unreachable.") {
    super(message);
    this.name = "AgentsRunUnreachableError";
  }
}

/**
 * Rate limited — server returned 429 or 503 from start_run_limiter (5 req/min).
 */
export class AgentsRateLimitedError extends Error {
  public readonly code = "AGENTS_RATE_LIMITED";

  constructor(message = "Too many requests. Please try again in a moment.") {
    super(message);
    this.name = "AgentsRateLimitedError";
  }
}

/**
 * Server error — 5xx generic response.
 */
export class AgentsServerError extends Error {
  public readonly code = "AGENTS_SERVER_ERROR";
  public readonly status: number;

  constructor(status: number, message = "Server error.") {
    super(message);
    this.name = "AgentsServerError";
    this.status = status;
  }
}

/**
 * Network error — fetch rejected (offline, CORS, DNS failure).
 */
export class AgentsNetworkError extends Error {
  public readonly code = "AGENTS_NETWORK_ERROR";

  constructor(message = "Network request failed.", public readonly cause?: unknown) {
    super(message);
    this.name = "AgentsNetworkError";
  }
}

/** Discriminated union of all typed Agents errors. */
export type AgentsError =
  | AgentsAuthExpiredError
  | AgentsForbiddenError
  | AgentsAgentNotFoundError
  | AgentsToolNotFoundError
  | AgentsToolNotApprovedError
  | AgentsAgentDisabledError
  | AgentsRunUnreachableError
  | AgentsRateLimitedError
  | AgentsServerError
  | AgentsNetworkError;

// ---------------------------------------------------------------------------
// Error mapper
// ---------------------------------------------------------------------------

/**
 * Maps an unknown fetch/domain error to a typed AgentsError.
 *
 * @param err - Raw caught value from a try/catch block.
 * @returns A typed domain error.
 */
export function mapAgentsError(err: unknown): AgentsError {
  if (err instanceof AgentsAuthExpiredError) return err;
  if (err instanceof AgentsForbiddenError) return err;
  if (err instanceof AgentsAgentNotFoundError) return err;
  if (err instanceof AgentsToolNotFoundError) return err;
  if (err instanceof AgentsToolNotApprovedError) return err;
  if (err instanceof AgentsAgentDisabledError) return err;
  if (err instanceof AgentsRunUnreachableError) return err;
  if (err instanceof AgentsRateLimitedError) return err;
  if (err instanceof AgentsServerError) return err;
  if (err instanceof AgentsNetworkError) return err;
  if (err instanceof TypeError) return new AgentsNetworkError(err.message, err);
  if (err instanceof Error) return new AgentsNetworkError(err.message, err);
  return new AgentsNetworkError("Unknown error");
}

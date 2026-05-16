/**
 * Hilo People — MCP feature domain errors.
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *
 * Responsibility: Typed error classes for MCP operations.
 *   mcpRepository.ts returns these via Result<T,E> patterns.
 *   Non-negotiables §error-handling: never catch generic Error — use typed domain errors.
 *
 * §D-T003-DATA-ERRORS (P04-S02-T003 task pack §5)
 *
 * Mirrors features/chat/data/errors.ts and features/auth/data/errors.ts patterns.
 * Source: TECHNICAL_GUIDE §6.2 — endpoint error codes (task pack §3.1–§3.2).
 */

// ---------------------------------------------------------------------------
// MCP error classes
// ---------------------------------------------------------------------------

/**
 * Session expired — server returned 401 after refresh exhausted.
 * authFetch single-flight exhausted; recovery is impossible without re-login.
 */
export class McpAuthExpiredError extends Error {
  public readonly code = "MCP_AUTH_EXPIRED";

  constructor(message = "Session expired. Please sign in again.") {
    super(message);
    this.name = "McpAuthExpiredError";
  }
}

/**
 * Forbidden — server returned 403 (role missing or insufficient).
 * Page-level: RequireRole catches this at routing. In-page 403 surfaces this.
 */
export class McpForbiddenError extends Error {
  public readonly code = "MCP_FORBIDDEN";

  constructor(message = "You do not have permission to perform this action.") {
    super(message);
    this.name = "McpForbiddenError";
  }
}

/**
 * Server not found — server returned 404 for POST /sync.
 * Only surfaced for sync actions; the LIST endpoint would simply omit it.
 */
export class McpServerNotFoundError extends Error {
  public readonly code = "MCP_SERVER_NOT_FOUND";

  constructor(message = "MCP server not found.") {
    super(message);
    this.name = "McpServerNotFoundError";
  }
}

/**
 * MCP server unreachable — backend returned 502.
 * Maps to existing i18n key errors:MCP_SERVER_UNREACHABLE.
 * Indicates the remote MCP endpoint (e.g. http://localhost:8080/mcp) is down.
 * This is an EXPECTED failure path per §3.5 + R-3 of the task pack.
 */
export class McpServerUnreachableError extends Error {
  public readonly code = "MCP_SERVER_UNREACHABLE";

  constructor(message = "Unable to connect to the MCP server.") {
    super(message);
    this.name = "McpServerUnreachableError";
  }
}

/**
 * Rate limited — server returned 429.
 * Sync endpoint is rate-limited per TECHNICAL_GUIDE §6.2.
 */
export class McpRateLimitedError extends Error {
  public readonly code = "MCP_RATE_LIMITED";

  constructor(message = "Too many sync requests. Please wait and try again.") {
    super(message);
    this.name = "McpRateLimitedError";
  }
}

/**
 * Server error — 5xx generic response.
 */
export class McpServerError extends Error {
  public readonly code = "MCP_SERVER_ERROR";
  public readonly status: number;

  constructor(status: number, message = "Server error.") {
    super(message);
    this.name = "McpServerError";
    this.status = status;
  }
}

/**
 * Network error — fetch rejected (offline, CORS, DNS failure).
 */
export class McpNetworkError extends Error {
  public readonly code = "MCP_NETWORK_ERROR";

  constructor(message = "Network request failed.", public readonly cause?: unknown) {
    super(message);
    this.name = "McpNetworkError";
  }
}

/** Discriminated union of all typed MCP errors. */
export type McpError =
  | McpAuthExpiredError
  | McpForbiddenError
  | McpServerNotFoundError
  | McpServerUnreachableError
  | McpRateLimitedError
  | McpServerError
  | McpNetworkError;

// ---------------------------------------------------------------------------
// Error mapper
// ---------------------------------------------------------------------------

/**
 * Maps an unknown fetch/domain error to a typed McpError.
 *
 * @param err - Raw caught value from a try/catch block.
 * @returns A typed domain error.
 */
export function mapMcpError(err: unknown): McpError {
  if (err instanceof McpAuthExpiredError) return err;
  if (err instanceof McpForbiddenError) return err;
  if (err instanceof McpServerNotFoundError) return err;
  if (err instanceof McpServerUnreachableError) return err;
  if (err instanceof McpRateLimitedError) return err;
  if (err instanceof McpServerError) return err;
  if (err instanceof McpNetworkError) return err;
  if (err instanceof TypeError) {
    return new McpNetworkError(err.message, err);
  }
  if (err instanceof Error) return new McpNetworkError(err.message, err);
  return new McpNetworkError("Unknown error");
}

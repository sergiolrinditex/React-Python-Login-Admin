/**
 * Hilo People — MCP feature domain types.
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *
 * Responsibility: Domain types for the MCP servers feature.
 *   Mirrors backend schemas.py ServerOut + SyncResponse exactly.
 *   No external imports — pure domain layer.
 *
 * §D-T003-DOMAIN-TYPES (P04-S02-T003 task pack §5)
 * §D-T004-DOMAIN-TYPES (P04-S02-T004 task pack §6) — added McpTransport, McpAuthType,
 *   CreateServerRequest per backend POST /api/v1/admin/ai/mcp/servers contract
 *   (schemas.py:64-86). Slice: P04-S02-T004 — McpWizardPage / Phase 4.
 *
 * Clean Architecture: domain layer — no React, no fetch, no external libs.
 *   Presentation and data layers import from here; domain imports nothing external.
 *
 * Wire contract source: TECHNICAL_GUIDE §6.2 + §3.1 + §6.3 of task pack.
 */

// Re-export Result type from auth domain for reuse (P-29 #2 pattern)
export type { Result } from "../../auth/domain/AuthRepository";

// ---------------------------------------------------------------------------
// Server status literal union
// Open string union for backward-compat with future backend statuses.
// ---------------------------------------------------------------------------

/** Status of an MCP server. Open union to tolerate future backend additions. */
export type McpServerStatus = "draft" | "active" | "error" | "inactive" | (string & {});

// ---------------------------------------------------------------------------
// MCP server — mirrors backend schemas.py ServerOut
// ---------------------------------------------------------------------------

/**
 * MCP server entity as returned by GET /api/v1/admin/ai/mcp/servers.
 *
 * Fields mirror backend ServerOut schema exactly (task pack §3.1).
 * No tool_count or risk_label — those are not in the list endpoint wire response.
 * §D-T003-TOOL-COUNT-TRANSIENT: tool_count lives in McpSyncResult only.
 */
export interface McpServer {
  /** UUID of the server record. */
  id: string;
  /** Human-readable name of the server. */
  name: string;
  /** Transport protocol: "http" | "sse" (backend wire value). */
  transport: string;
  /** Endpoint URL (null for stdio servers). */
  endpoint: string | null;
  /** Server status. */
  status: McpServerStatus;
  /** ISO 8601 timestamp of last successful sync, or null. */
  last_sync_at: string | null;
  /** UUID of the user who created the server, or null. */
  created_by: string | null;
  /** Whether a credential is configured for this server. */
  has_credential: boolean;
  /** Auth type used for this server, or null. */
  auth_type: "none" | "api_key" | "bearer" | "oauth2" | null;
}

// ---------------------------------------------------------------------------
// Sync result — mirrors backend schemas.py SyncResponse
// ---------------------------------------------------------------------------

/**
 * Response from POST /api/v1/admin/ai/mcp/servers/{id}/sync (task pack §3.2).
 *
 * §D-T003-TOOL-COUNT-TRANSIENT: tools_count is sourced from this type only.
 *   The list endpoint does NOT return tool counts. This result is transiently
 *   stored per-row in McpServersPage state after a sync action.
 */
export interface McpSyncResult {
  /** Number of tools discovered from the server. */
  tools_count: number;
  /** Number of resources discovered from the server. */
  resources_count: number;
  /** Number of prompts discovered from the server. */
  prompts_count: number;
  /** Server status after sync. */
  status: McpServerStatus;
}

// ---------------------------------------------------------------------------
// Wizard create types — §D-T004-DOMAIN-TYPES
// Mirrors backend CreateServerRequest (schemas.py:64) exactly.
// stdio is intentionally excluded per instrucciones.md §3.1 line 99.
// ---------------------------------------------------------------------------

/**
 * Transport protocol for MCP servers.
 * stdio is excluded — backend supports it but UI must not offer it (§3.1 line 99).
 */
export type McpTransport = "http" | "sse";

/**
 * Authentication type for MCP server credentials.
 * Mirrors backend auth.type enum (schemas.py:71).
 */
export type McpAuthType = "none" | "api_key" | "bearer" | "oauth2";

/**
 * Auth sub-object for CreateServerRequest.
 * secret is required (non-empty) unless type='none'.
 * refresh_token is optional; only meaningful for oauth2.
 */
export interface McpCreateAuth {
  /** Auth method. */
  type: McpAuthType;
  /**
   * Credential secret.
   * null when type='none'; non-null required for api_key/bearer/oauth2.
   * NEVER logged, NEVER stored in client storage beyond form lifetime.
   */
  secret: string | null;
  /** Refresh token for OAuth2. null for all other types. */
  refresh_token: string | null;
}

/**
 * Wire DTO for POST /api/v1/admin/ai/mcp/servers.
 *
 * Mirrors backend CreateServerRequest (schemas.py:64) with extra="forbid".
 * Validated on frontend by CreateServerFormSchema (Zod).
 *
 * §D-T004-DOMAIN-TYPES
 */
export interface CreateServerRequest {
  /** Human-readable server name (1..200 chars). */
  name: string;
  /** Transport protocol. stdio excluded (instrucciones §3.1 line 99). */
  transport: McpTransport;
  /** URL of MCP HTTP/SSE endpoint (1..2000 chars). */
  endpoint: string;
  /** Auth configuration. */
  auth: McpCreateAuth;
}

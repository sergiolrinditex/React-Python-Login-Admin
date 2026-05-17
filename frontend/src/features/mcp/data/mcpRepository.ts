/**
 * Hilo People — MCP repository (concrete HTTP adapter).
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *
 * Responsibility: HTTP adapter for MCP server operations.
 *   Calls GET /api/v1/admin/ai/mcp/servers and POST .../servers/{id}/sync via authFetch.
 *   Returns Result<T, McpError> — never throws to presentation layer.
 *   Mirrors chatRepository.ts pattern: BEFORE/AFTER/ERROR logging, Result shape.
 *
 * §D-T003-DATA-REPO (P04-S02-T003 task pack §5)
 * §D-T004-DATA-REPO (P04-S02-T004 task pack §6) — added createServer() function.
 *   Handles POST /api/v1/admin/ai/mcp/servers: 201, 400, 422, 429, 401, 403, 5xx.
 *   422 parsing: Pydantic-native shape { detail: [{loc, msg, type}] } NOT app envelope.
 *   400 MCP_ENDPOINT_NOT_ALLOWED mapped to McpEndpointNotAllowedError.
 *   Secret NEVER logged, NEVER stored; only auth_type is logged (§D-T004-SECRET-FIELD).
 *   Slice: P04-S02-T004 — McpWizardPage / Phase 4.
 *
 * Clean Architecture: DATA layer for the MCP feature.
 *   Presentation hooks depend on this module, not the raw HTTP client.
 *
 * Security:
 *   - Uses authFetch (X-Request-ID, credentials:include, Bearer injection, single-flight 401).
 *   - Relative URL per ADR-002 (same-origin via vite proxy in dev, Nginx in prod).
 *   - NEVER hardcode http://localhost:8000 here.
 *   - NEVER log endpoint URLs with credentials, auth secrets, or PII.
 *   - For createServer: log auth_type only; NEVER log secret or refresh_token.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR on every public method.
 */

import type { Result } from "../domain/types";
import type { McpServer, McpSyncResult, CreateServerRequest } from "../domain/types";
import { authFetch } from "../../auth/data/httpClient";
import {
  McpAuthExpiredError,
  McpForbiddenError,
  McpServerNotFoundError,
  McpServerUnreachableError,
  McpRateLimitedError,
  McpServerError,
  McpValidationError,
  McpEndpointNotAllowedError,
  mapMcpError,
  type McpError,
} from "./errors";
import { logVerbose, logWarn, logError } from "./logger";

// ---------------------------------------------------------------------------
// Constants — ADR-002 relative URLs
// ---------------------------------------------------------------------------

const MCP_SERVERS_URL = "/api/v1/admin/ai/mcp/servers";

// ---------------------------------------------------------------------------
// Helper: safely read response JSON
// ---------------------------------------------------------------------------

async function _safeJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) throw new Error("Empty response body");
  return JSON.parse(text) as T;
}

// ---------------------------------------------------------------------------
// Public: listServers
// ---------------------------------------------------------------------------

/**
 * Calls GET /api/v1/admin/ai/mcp/servers.
 *
 * Returns Result.ok([McpServer]) on 200.
 * Returns typed Result.err for all failure paths (401, 403, 5xx, network).
 *
 * Note: the response does NOT include tool_count or risk_label per server.
 * §D-T003-TOOL-COUNT-TRANSIENT: tool_count only available after POST /sync.
 *
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns Result<McpServer[], McpError>
 */
export async function listServers(
  onAuthFailure: () => void,
): Promise<Result<McpServer[], McpError>> {
  logVerbose("mcp.repo.listServers.start");

  try {
    const response = await authFetch(
      MCP_SERVERS_URL,
      { method: "GET" },
      { onAuthFailure },
    );

    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 401) {
      logWarn("mcp.repo.listServers.auth_expired", {
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new McpAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("mcp.repo.listServers.forbidden", {
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new McpForbiddenError() };
    }

    if (!response.ok) {
      logError("mcp.repo.listServers.server_error", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new McpServerError(response.status) };
    }

    const body = await _safeJson<{ data: McpServer[]; meta: { request_id: string } }>(response);
    logVerbose("mcp.repo.listServers.ok", {
      count: body.data.length,
      request_id: requestId,
    });

    return { ok: true, value: body.data };
  } catch (err: unknown) {
    const domainErr = mapMcpError(err);
    logError("mcp.repo.listServers.error", {
      error: domainErr.code,
    });
    return { ok: false, error: domainErr };
  }
}

// ---------------------------------------------------------------------------
// Public: syncServer
// ---------------------------------------------------------------------------

/**
 * Calls POST /api/v1/admin/ai/mcp/servers/{id}/sync.
 *
 * Returns Result.ok(McpSyncResult) on 200 — contains tools_count, resources_count,
 *   prompts_count, and updated status.
 * Returns typed Result.err for 401, 403, 404, 429, 502, 5xx, and network failures.
 *
 * The 502 response (MCP_SERVER_UNREACHABLE) is the EXPECTED failure when the remote
 * MCP endpoint is not running. This is a real-world path per task pack §3.5 + R-3.
 *
 * @param id - UUID of the MCP server to sync.
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns Result<McpSyncResult, McpError>
 */
export async function syncServer(
  id: string,
  onAuthFailure: () => void,
): Promise<Result<McpSyncResult, McpError>> {
  logVerbose("mcp.repo.syncServer.start", { server_id: id });

  try {
    const response = await authFetch(
      `${MCP_SERVERS_URL}/${id}/sync`,
      { method: "POST" },
      { onAuthFailure },
    );

    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 401) {
      logWarn("mcp.repo.syncServer.auth_expired", {
        server_id: id,
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new McpAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("mcp.repo.syncServer.forbidden", {
        server_id: id,
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new McpForbiddenError() };
    }

    if (response.status === 404) {
      logWarn("mcp.repo.syncServer.not_found", {
        server_id: id,
        request_id: requestId,
      });
      return { ok: false, error: new McpServerNotFoundError() };
    }

    if (response.status === 429) {
      logWarn("mcp.repo.syncServer.rate_limited", {
        server_id: id,
        request_id: requestId,
      });
      return { ok: false, error: new McpRateLimitedError() };
    }

    if (response.status === 502) {
      // Expected real-world failure: remote MCP endpoint not reachable.
      // Maps to i18n key errors:MCP_SERVER_UNREACHABLE.
      logWarn("mcp.repo.syncServer.unreachable", {
        server_id: id,
        request_id: requestId,
      });
      return { ok: false, error: new McpServerUnreachableError() };
    }

    if (!response.ok) {
      logError("mcp.repo.syncServer.server_error", {
        server_id: id,
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new McpServerError(response.status) };
    }

    const body = await _safeJson<{ data: McpSyncResult; meta: { request_id: string } }>(response);
    logVerbose("mcp.repo.syncServer.ok", {
      server_id: id,
      tools_count: body.data.tools_count,
      status: body.data.status,
      request_id: requestId,
    });

    return { ok: true, value: body.data };
  } catch (err: unknown) {
    const domainErr = mapMcpError(err);
    logError("mcp.repo.syncServer.error", {
      server_id: id,
      error: domainErr.code,
    });
    return { ok: false, error: domainErr };
  }
}

// ---------------------------------------------------------------------------
// Public: createServer — §D-T004-DATA-REPO
// ---------------------------------------------------------------------------

/**
 * Calls POST /api/v1/admin/ai/mcp/servers to register a new MCP server.
 *
 * Returns Result.ok(McpServer) on 201.
 * Returns typed Result.err for 400 (allowlist), 401, 403, 422 (validation),
 *   429 (rate limit), 5xx (server error), and network failures.
 *
 * 422 parsing: Pydantic-native shape { detail: [{loc, msg, type}] }.
 *   Each loc array is mapped to an RHF field name and stored in McpValidationError.fieldErrors.
 * §D-T004-422-PARSE (R-2 mitigation).
 *
 * Security: secret and refresh_token are NEVER logged.
 * Only auth_type is logged (§D-T004-SECRET-FIELD, §D-T004-SECRET-NEVER-PERSISTED).
 *
 * @param req - CreateServerRequest wire DTO.
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns Result<McpServer, McpError>
 */
export async function createServer(
  req: CreateServerRequest,
  onAuthFailure: () => void,
): Promise<Result<McpServer, McpError>> {
  // BEFORE log — auth_type logged only; secret/refresh_token NEVER logged
  logVerbose("mcp.repo.createServer.start", {
    transport: req.transport,
    auth_type: req.auth.type,
  });

  try {
    const response = await authFetch(
      MCP_SERVERS_URL,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      },
      { onAuthFailure },
    );

    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 401) {
      logWarn("mcp.repo.createServer.auth_expired", {
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new McpAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("mcp.repo.createServer.forbidden", {
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new McpForbiddenError() };
    }

    if (response.status === 400) {
      // §D-T004-400-UNIT-ONLY: MCP_ENDPOINT_NOT_ALLOWED
      // Only reached when MCP_ALLOWLIST_DOMAINS is set (not default dev env).
      logWarn("mcp.repo.createServer.endpoint_not_allowed", {
        status: 400,
        request_id: requestId,
      });
      return { ok: false, error: new McpEndpointNotAllowedError() };
    }

    if (response.status === 422) {
      // §D-T004-422-PARSE: Pydantic-native validation error (NOT app envelope)
      // Shape: { detail: [{ loc: string[], msg: string, type: string }] }
      interface PydanticDetail {
        loc: string[];
        msg: string;
        type: string;
      }
      interface PydanticError422 {
        detail: PydanticDetail[];
      }

      const body = await _safeJson<PydanticError422>(response);
      const fieldErrors: Record<string, string> = {};

      for (const item of body.detail) {
        // loc example: ["body", "auth", "secret"] → field name is last element
        const field = item.loc[item.loc.length - 1] ?? "form";
        // Map backend field names to RHF field names
        const rhfField = field === "secret" ? "secret"
          : field === "refresh_token" ? "refreshToken"
          : field === "name" ? "name"
          : field === "transport" ? "transport"
          : field === "endpoint" ? "endpoint"
          : field === "type" ? "authType"
          : "form";
        fieldErrors[rhfField] = item.msg;
      }

      logWarn("mcp.repo.createServer.validation_error", {
        field_count: Object.keys(fieldErrors).length,
        request_id: requestId,
      });
      return { ok: false, error: new McpValidationError(fieldErrors) };
    }

    if (response.status === 429) {
      logWarn("mcp.repo.createServer.rate_limited", {
        status: 429,
        request_id: requestId,
      });
      return { ok: false, error: new McpRateLimitedError() };
    }

    if (!response.ok) {
      logError("mcp.repo.createServer.server_error", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new McpServerError(response.status) };
    }

    // 201 Created — ServerOut in envelope { data, meta }
    const body = await _safeJson<{ data: McpServer; meta: { request_id: string } }>(response);

    // AFTER log — id and status only; secret already not in response body
    logVerbose("mcp.repo.createServer.ok", {
      server_id: body.data.id,
      status: body.data.status,
      has_credential: body.data.has_credential,
      request_id: requestId,
    });

    return { ok: true, value: body.data };
  } catch (err: unknown) {
    const domainErr = mapMcpError(err);
    logError("mcp.repo.createServer.error", {
      error: domainErr.code,
    });
    return { ok: false, error: domainErr };
  }
}

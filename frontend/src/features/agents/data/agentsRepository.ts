/**
 * Hilo People — Agents repository (concrete HTTP adapter).
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: HTTP adapter for AI agents operations.
 *   Calls GET /api/v1/admin/ai/agents, PATCH .../agents/{id}/tools,
 *   and POST /api/v1/agents/runs via authFetch.
 *   Returns Result<T, AgentsError> — never throws to presentation layer.
 *   Mirrors mcpRepository.ts pattern: BEFORE/AFTER/ERROR logging, Result shape.
 *
 * §D-T005-REPO (P04-S02-T005 task pack §8.1)
 *
 * Clean Architecture: DATA layer for the agents feature.
 *   Presentation hooks depend on this module, not the raw HTTP client.
 *
 * Security:
 *   - Uses authFetch (X-Request-ID, credentials:include, Bearer injection, single-flight 401).
 *   - Relative URL per ADR-002 (same-origin via vite proxy in dev, Nginx in prod).
 *   - NEVER hardcode http://localhost:8000 here.
 *   - §D-T005-LOGS-PII-CLEAN: never log tool_id values, never log agent.name, never log input text.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR on every public method.
 */

import type { Result } from "../domain/types";
import type { Agent, UpdateAgentToolsRequest, StartAgentRunRequest, StartAgentRunResult } from "../domain/types";
import { authFetch } from "../../auth/data/httpClient";
import {
  AgentsAuthExpiredError,
  AgentsForbiddenError,
  AgentsAgentNotFoundError,
  AgentsToolNotFoundError,
  AgentsToolNotApprovedError,
  AgentsAgentDisabledError,
  AgentsRunUnreachableError,
  AgentsRateLimitedError,
  AgentsServerError,
  mapAgentsError,
  type AgentsError,
} from "./errors";
import { logVerbose, logWarn, logError } from "./logger";

// ---------------------------------------------------------------------------
// Constants — ADR-002 relative URLs
// ---------------------------------------------------------------------------

const AGENTS_URL = "/api/v1/admin/ai/agents";
const AGENTS_TOOLS_URL = (id: string): string => `/api/v1/admin/ai/agents/${id}/tools`;
const AGENT_RUNS_URL = "/api/v1/agents/runs";

// ---------------------------------------------------------------------------
// Helper: safely read response JSON
// ---------------------------------------------------------------------------

async function _safeJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) throw new Error("Empty response body");
  return JSON.parse(text) as T;
}

// ---------------------------------------------------------------------------
// Helper: parse error code from backend error body
// ---------------------------------------------------------------------------

async function _parseErrorCode(res: Response): Promise<string | null> {
  try {
    const text = await res.text();
    if (!text) return null;
    const body = JSON.parse(text) as { error?: string; code?: string };
    return body.error ?? body.code ?? null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Public: listAgents
// ---------------------------------------------------------------------------

/**
 * Calls GET /api/v1/admin/ai/agents.
 *
 * Returns Result.ok([Agent]) on 200.
 * Returns typed Result.err for all failure paths (401, 403, 5xx, network).
 *
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns Result<Agent[], AgentsError>
 */
export async function listAgents(
  onAuthFailure: () => void,
): Promise<Result<Agent[], AgentsError>> {
  logVerbose("agents.repo.listAgents.start");

  try {
    const response = await authFetch(
      AGENTS_URL,
      { method: "GET" },
      { onAuthFailure },
    );

    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 401) {
      logWarn("agents.repo.listAgents.auth_expired", {
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("agents.repo.listAgents.forbidden", {
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsForbiddenError() };
    }

    if (!response.ok) {
      logError("agents.repo.listAgents.server_error", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsServerError(response.status) };
    }

    const body = await _safeJson<{ data: Agent[]; meta: { request_id: string } }>(response);
    logVerbose("agents.repo.listAgents.ok", {
      count: body.data.length,
      request_id: requestId,
    });

    return { ok: true, value: body.data };
  } catch (err: unknown) {
    const domainErr = mapAgentsError(err);
    logError("agents.repo.listAgents.error", { error: domainErr.code });
    return { ok: false, error: domainErr };
  }
}

// ---------------------------------------------------------------------------
// Public: updateAgentTools
// ---------------------------------------------------------------------------

/**
 * Calls PATCH /api/v1/admin/ai/agents/{agentId}/tools.
 *
 * Body: { tool_ids: string[] } (set-replace; empty array unbinds all).
 * Returns Result.ok(Agent) on 200 — full agent with refreshed bound_tools.
 * Returns typed Result.err for 400/401/403/404/5xx.
 *
 * §D-T005-REPO: maps AGENT_TOOL_NOT_FOUND and AGENT_TOOL_NOT_APPROVED per §6.2.
 *
 * @param agentId - UUID of the agent to update.
 * @param request - UpdateAgentToolsRequest with tool_ids.
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns Result<Agent, AgentsError>
 */
export async function updateAgentTools(
  agentId: string,
  request: UpdateAgentToolsRequest,
  onAuthFailure: () => void,
): Promise<Result<Agent, AgentsError>> {
  logVerbose("agents.repo.updateAgentTools.start", {
    agent_id: agentId,
    tool_count: request.tool_ids.length,
    // PII-CLEAN: never log tool_id values
  });

  try {
    const response = await authFetch(
      AGENTS_TOOLS_URL(agentId),
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      },
      { onAuthFailure },
    );

    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 401) {
      logWarn("agents.repo.updateAgentTools.auth_expired", {
        agent_id: agentId,
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("agents.repo.updateAgentTools.forbidden", {
        agent_id: agentId,
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsForbiddenError() };
    }

    if (response.status === 404) {
      logWarn("agents.repo.updateAgentTools.not_found", {
        agent_id: agentId,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsAgentNotFoundError() };
    }

    if (response.status === 400) {
      // Distinguish AGENT_TOOL_NOT_FOUND vs AGENT_TOOL_NOT_APPROVED
      const errorCode = await _parseErrorCode(response);
      logWarn("agents.repo.updateAgentTools.validation_error", {
        agent_id: agentId,
        error_code: errorCode,
        request_id: requestId,
      });
      if (errorCode === "AGENT_TOOL_NOT_APPROVED") {
        return { ok: false, error: new AgentsToolNotApprovedError() };
      }
      return { ok: false, error: new AgentsToolNotFoundError() };
    }

    if (!response.ok) {
      logError("agents.repo.updateAgentTools.server_error", {
        agent_id: agentId,
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsServerError(response.status) };
    }

    const body = await _safeJson<{ data: Agent; meta: { request_id: string } }>(response);
    logVerbose("agents.repo.updateAgentTools.ok", {
      agent_id: agentId,
      bound_tool_count: body.data.bound_tools.length,
      request_id: requestId,
    });

    return { ok: true, value: body.data };
  } catch (err: unknown) {
    const domainErr = mapAgentsError(err);
    logError("agents.repo.updateAgentTools.error", {
      agent_id: agentId,
      error: domainErr.code,
    });
    return { ok: false, error: domainErr };
  }
}

// ---------------------------------------------------------------------------
// Public: startAgentRun
// ---------------------------------------------------------------------------

/**
 * Calls POST /api/v1/agents/runs.
 *
 * Body: { agent_id, input } (input 1..4000 chars; validated client-side too).
 * Returns Result.ok(StartAgentRunResult) on 200.
 * Returns typed Result.err for 400/401/403/404/409/429/502/5xx.
 *
 * §D-T005-502-INTENT: 502 AGENT_RUN_FAILED is expected evidence in dev sandbox.
 * §D-T005-BACKEND-NEW-409: 409 AGENT_DISABLED is from router_runs.py:104 (not in doc table).
 *
 * @param request - StartAgentRunRequest with agent_id and input.
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @returns Result<StartAgentRunResult, AgentsError>
 */
export async function startAgentRun(
  request: StartAgentRunRequest,
  onAuthFailure: () => void,
): Promise<Result<StartAgentRunResult, AgentsError>> {
  // PII-CLEAN: log agent_id only — never log input text
  logVerbose("agents.repo.startAgentRun.start", {
    agent_id: request.agent_id,
  });

  try {
    const response = await authFetch(
      AGENT_RUNS_URL,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      },
      { onAuthFailure },
    );

    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 401) {
      logWarn("agents.repo.startAgentRun.auth_expired", {
        agent_id: request.agent_id,
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("agents.repo.startAgentRun.forbidden", {
        agent_id: request.agent_id,
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsForbiddenError() };
    }

    if (response.status === 404) {
      logWarn("agents.repo.startAgentRun.not_found", {
        agent_id: request.agent_id,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsAgentNotFoundError() };
    }

    if (response.status === 409) {
      // §D-T005-BACKEND-NEW-409: AGENT_DISABLED — not in TECHNICAL_GUIDE §6.2 but in router_runs.py:104
      logWarn("agents.repo.startAgentRun.agent_disabled", {
        agent_id: request.agent_id,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsAgentDisabledError() };
    }

    if (response.status === 429 || response.status === 503) {
      logWarn("agents.repo.startAgentRun.rate_limited", {
        agent_id: request.agent_id,
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsRateLimitedError() };
    }

    if (response.status === 502) {
      // §D-T005-502-INTENT: expected in dev sandbox — DeepAgents/LangGraph downstream unreachable
      logWarn("agents.repo.startAgentRun.unreachable", {
        agent_id: request.agent_id,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsRunUnreachableError() };
    }

    if (response.status === 400) {
      logWarn("agents.repo.startAgentRun.validation_error", {
        agent_id: request.agent_id,
        status: 400,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsServerError(400) };
    }

    if (!response.ok) {
      logError("agents.repo.startAgentRun.server_error", {
        agent_id: request.agent_id,
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new AgentsServerError(response.status) };
    }

    const body = await _safeJson<{ data: StartAgentRunResult; meta: { request_id: string } }>(response);
    logVerbose("agents.repo.startAgentRun.ok", {
      agent_id: request.agent_id,
      run_id: body.data.run_id,
      status: body.data.status,
      request_id: requestId,
    });

    return { ok: true, value: body.data };
  } catch (err: unknown) {
    const domainErr = mapAgentsError(err);
    logError("agents.repo.startAgentRun.error", {
      agent_id: request.agent_id,
      error: domainErr.code,
    });
    return { ok: false, error: domainErr };
  }
}

/**
 * Hilo People — agentsRepository tests.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: Unit tests for the agents HTTP repository adapter.
 *   Tests the Result<T,E> contract for listAgents, updateAgentTools, startAgentRun.
 *   authFetch is mocked at the module boundary (HTTP boundary, not business logic).
 *
 * §D-T005-TESTS-REPO (P04-S02-T005 task pack §10)
 *   R01 listAgents 200 → Result.ok array
 *   R02 listAgents 401 → AgentsAuthExpiredError
 *   R03 listAgents 403 → AgentsForbiddenError
 *   R04 listAgents 500 → AgentsServerError
 *   R05 updateAgentTools 200 → Result.ok agent with bound_tools
 *   R06 updateAgentTools 400 AGENT_TOOL_NOT_APPROVED → AgentsToolNotApprovedError
 *   R07 updateAgentTools 404 → AgentsAgentNotFoundError
 *   R08 startAgentRun 200 → Result.ok with run_id + status
 *   R09 startAgentRun 409 AGENT_DISABLED → AgentsAgentDisabledError
 *   R10 startAgentRun 502 → AgentsRunUnreachableError
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  AgentsAuthExpiredError,
  AgentsForbiddenError,
  AgentsAgentNotFoundError,
  AgentsToolNotFoundError,
  AgentsToolNotApprovedError,
  AgentsAgentDisabledError,
  AgentsRunUnreachableError,
  AgentsServerError,
  AgentsNetworkError,
} from "../data/errors";

// ---------------------------------------------------------------------------
// Mock authFetch
// ---------------------------------------------------------------------------

vi.mock("../../auth/data/httpClient", () => ({
  authFetch: vi.fn(),
}));

import { authFetch } from "../../auth/data/httpClient";
import { listAgents, updateAgentTools, startAgentRun } from "../data/agentsRepository";

const mockAuthFetch = vi.mocked(authFetch);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  const responseHeaders = new Headers({ "x-request-id": "test-req-id", ...headers });
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: responseHeaders,
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_BOUND_TOOL = {
  id: "tool-uuid-1",
  name: "list_employees",
  server_name: "sandbox_readonly",
  enabled: true,
  requires_approval: false,
  risk_level: "low",
};

const MOCK_AGENT = {
  id: "agent-uuid-1",
  name: "people_helper",
  description: "Helps with People HR questions",
  enabled: true,
  config: {},
  bound_tools: [MOCK_BOUND_TOOL],
};

const MOCK_RUN_RESULT = {
  run_id: "run-uuid-1",
  status: "pending",
};

// ---------------------------------------------------------------------------
// Tests — listAgents
// ---------------------------------------------------------------------------

describe("agentsRepository.listAgents", () => {
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("R01 — 200 → Result.ok with mapped agent array", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, { data: [MOCK_AGENT], meta: { request_id: "r1" } }),
    );

    const result = await listAgents(onAuthFailure);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value).toHaveLength(1);
      expect(result.value[0].id).toBe("agent-uuid-1");
      expect(result.value[0].enabled).toBe(true);
      expect(result.value[0].bound_tools).toHaveLength(1);
    }
  });

  it("R02 — 401 → Result.err AgentsAuthExpiredError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(401, {}));

    const result = await listAgents(onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AgentsAuthExpiredError);
      expect(result.error.code).toBe("AGENTS_AUTH_EXPIRED");
    }
  });

  it("R03 — 403 → Result.err AgentsForbiddenError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(403, {}));

    const result = await listAgents(onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AgentsForbiddenError);
      expect(result.error.code).toBe("AGENTS_FORBIDDEN");
    }
  });

  it("R04 — 500 → Result.err AgentsServerError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(500, {}));

    const result = await listAgents(onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AgentsServerError);
      expect((result.error as AgentsServerError).status).toBe(500);
    }
  });

  it("R04b — network failure → Result.err AgentsNetworkError", async () => {
    mockAuthFetch.mockImplementationOnce(() =>
      Promise.reject(new TypeError("Failed to fetch")),
    );

    const result = await listAgents(onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AgentsNetworkError);
      expect(result.error.code).toBe("AGENTS_NETWORK_ERROR");
    }
  });
});

// ---------------------------------------------------------------------------
// Tests — updateAgentTools
// ---------------------------------------------------------------------------

describe("agentsRepository.updateAgentTools", () => {
  const onAuthFailure = vi.fn();
  const AGENT_ID = "agent-uuid-1";

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("R05 — 200 → Result.ok agent with refreshed bound_tools", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, { data: MOCK_AGENT, meta: { request_id: "r1" } }),
    );

    const result = await updateAgentTools(
      AGENT_ID,
      { tool_ids: ["tool-uuid-1"] },
      onAuthFailure,
    );

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.id).toBe("agent-uuid-1");
      expect(result.value.bound_tools).toHaveLength(1);
    }
  });

  it("R06 — 400 AGENT_TOOL_NOT_APPROVED → AgentsToolNotApprovedError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(400, { error: "AGENT_TOOL_NOT_APPROVED", details: { field: "tool_ids" } }),
    );

    const result = await updateAgentTools(
      AGENT_ID,
      { tool_ids: ["unapproved-tool-id"] },
      onAuthFailure,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AgentsToolNotApprovedError);
      expect(result.error.code).toBe("AGENT_TOOL_NOT_APPROVED");
    }
  });

  it("R06b — 400 AGENT_TOOL_NOT_FOUND → AgentsToolNotFoundError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(400, { error: "AGENT_TOOL_NOT_FOUND", details: { field: "tool_ids" } }),
    );

    const result = await updateAgentTools(
      AGENT_ID,
      { tool_ids: ["nonexistent-tool-id"] },
      onAuthFailure,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AgentsToolNotFoundError);
      expect(result.error.code).toBe("AGENT_TOOL_NOT_FOUND");
    }
  });

  it("R07 — 404 → AgentsAgentNotFoundError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(404, {}));

    const result = await updateAgentTools(
      AGENT_ID,
      { tool_ids: [] },
      onAuthFailure,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AgentsAgentNotFoundError);
      expect(result.error.code).toBe("AGENT_NOT_FOUND");
    }
  });
});

// ---------------------------------------------------------------------------
// Tests — startAgentRun
// ---------------------------------------------------------------------------

describe("agentsRepository.startAgentRun", () => {
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("R08 — 200 → Result.ok with run_id and status", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, { data: MOCK_RUN_RESULT, meta: { request_id: "r1" } }),
    );

    const result = await startAgentRun(
      { agent_id: "agent-uuid-1", input: "ping" },
      onAuthFailure,
    );

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.run_id).toBe("run-uuid-1");
      expect(result.value.status).toBe("pending");
    }
  });

  it("R09 — 409 AGENT_DISABLED → AgentsAgentDisabledError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(409, { error: "AGENT_DISABLED" }));

    const result = await startAgentRun(
      { agent_id: "agent-uuid-1", input: "ping" },
      onAuthFailure,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AgentsAgentDisabledError);
      expect(result.error.code).toBe("AGENT_DISABLED");
    }
  });

  it("R10 — 502 → AgentsRunUnreachableError (expected dev sandbox path)", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(502, { error: "AGENT_RUN_FAILED" }));

    const result = await startAgentRun(
      { agent_id: "agent-uuid-1", input: "ping" },
      onAuthFailure,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AgentsRunUnreachableError);
      expect(result.error.code).toBe("AGENT_RUN_FAILED");
    }
  });
});

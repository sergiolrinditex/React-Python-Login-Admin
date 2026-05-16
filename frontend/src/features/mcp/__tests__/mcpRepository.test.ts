/**
 * Hilo People — mcpRepository tests.
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *
 * Responsibility: Unit tests for the MCP HTTP repository adapter.
 *   Tests the Result<T,E> contract for both listServers and syncServer.
 *   authFetch is mocked at the module boundary (HTTP boundary, not business logic).
 *
 * §D-T003-TESTS-REPO (P04-S02-T003 task pack §5)
 *   R01 listServers 200 → Result.ok array
 *   R02 listServers 401 → McpAuthExpiredError
 *   R03 listServers 403 → McpForbiddenError
 *   R04 listServers 500 → McpServerError
 *   R05 listServers network failure → McpNetworkError
 *   R06 syncServer 200 → Result.ok with tools_count
 *   R07 syncServer 404 → McpServerNotFoundError
 *   R08 syncServer 502 → McpServerUnreachableError
 *   R09 syncServer 429 → McpRateLimitedError
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  McpAuthExpiredError,
  McpForbiddenError,
  McpServerNotFoundError,
  McpServerUnreachableError,
  McpRateLimitedError,
  McpServerError,
  McpNetworkError,
} from "../data/errors";

// ---------------------------------------------------------------------------
// Mock authFetch
// ---------------------------------------------------------------------------

vi.mock("../../auth/data/httpClient", () => ({
  authFetch: vi.fn(),
}));

import { authFetch } from "../../auth/data/httpClient";
import { listServers, syncServer } from "../data/mcpRepository";

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

function makeNetworkError(): never {
  throw new TypeError("Failed to fetch");
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_SERVER = {
  id: "server-uuid-1",
  name: "sandbox_readonly",
  transport: "http",
  endpoint: "http://localhost:8080/mcp",
  status: "active",
  last_sync_at: null,
  created_by: null,
  has_credential: false,
  auth_type: null,
};

const MOCK_SYNC_RESULT = {
  tools_count: 5,
  resources_count: 2,
  prompts_count: 1,
  status: "active",
};

// ---------------------------------------------------------------------------
// Tests — listServers
// ---------------------------------------------------------------------------

describe("mcpRepository.listServers", () => {
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("R01 — 200 → Result.ok with mapped server array", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, { data: [MOCK_SERVER], meta: { request_id: "r1" } }),
    );

    const result = await listServers(onAuthFailure);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value).toHaveLength(1);
      expect(result.value[0].id).toBe("server-uuid-1");
      expect(result.value[0].name).toBe("sandbox_readonly");
      expect(result.value[0].transport).toBe("http");
    }
  });

  it("R02 — 401 → Result.err McpAuthExpiredError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(401, {}));

    const result = await listServers(onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(McpAuthExpiredError);
      expect(result.error.code).toBe("MCP_AUTH_EXPIRED");
    }
  });

  it("R03 — 403 → Result.err McpForbiddenError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(403, {}));

    const result = await listServers(onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(McpForbiddenError);
      expect(result.error.code).toBe("MCP_FORBIDDEN");
    }
  });

  it("R04 — 500 → Result.err McpServerError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(500, {}));

    const result = await listServers(onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(McpServerError);
      expect((result.error as McpServerError).status).toBe(500);
    }
  });

  it("R05 — network failure → Result.err McpNetworkError", async () => {
    mockAuthFetch.mockImplementationOnce(() => {
      makeNetworkError();
      return Promise.reject(new TypeError("Failed to fetch"));
    });

    const result = await listServers(onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(McpNetworkError);
      expect(result.error.code).toBe("MCP_NETWORK_ERROR");
    }
  });
});

// ---------------------------------------------------------------------------
// Tests — syncServer
// ---------------------------------------------------------------------------

describe("mcpRepository.syncServer", () => {
  const onAuthFailure = vi.fn();
  const SERVER_ID = "server-uuid-1";

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("R06 — 200 → Result.ok with tools_count", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, { data: MOCK_SYNC_RESULT, meta: { request_id: "r1" } }),
    );

    const result = await syncServer(SERVER_ID, onAuthFailure);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.tools_count).toBe(5);
      expect(result.value.resources_count).toBe(2);
      expect(result.value.status).toBe("active");
    }
  });

  it("R07 — 404 → Result.err McpServerNotFoundError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(404, {}));

    const result = await syncServer(SERVER_ID, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(McpServerNotFoundError);
      expect(result.error.code).toBe("MCP_SERVER_NOT_FOUND");
    }
  });

  it("R08 — 502 → Result.err McpServerUnreachableError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(502, {}));

    const result = await syncServer(SERVER_ID, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(McpServerUnreachableError);
      expect(result.error.code).toBe("MCP_SERVER_UNREACHABLE");
    }
  });

  it("R09 — 429 → Result.err McpRateLimitedError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(429, {}));

    const result = await syncServer(SERVER_ID, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(McpRateLimitedError);
      expect(result.error.code).toBe("MCP_RATE_LIMITED");
    }
  });
});

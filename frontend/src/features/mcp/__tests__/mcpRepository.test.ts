/**
 * Hilo People — mcpRepository tests.
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *   Updated: P04-S02-T004 — McpWizardPage / Phase 4.
 *
 * Responsibility: Unit tests for the MCP HTTP repository adapter.
 *   Tests the Result<T,E> contract for listServers, syncServer, and createServer.
 *   authFetch is mocked at the module boundary (HTTP boundary, not business logic).
 *
 * §D-T003-TESTS-REPO (P04-S02-T003 task pack §5)
 * §D-T004-TESTS-REPO (P04-S02-T004 task pack §6)
 *   R01 listServers 200 → Result.ok array
 *   R02 listServers 401 → McpAuthExpiredError
 *   R03 listServers 403 → McpForbiddenError
 *   R04 listServers 500 → McpServerError
 *   R05 listServers network failure → McpNetworkError
 *   R06 syncServer 200 → Result.ok with tools_count
 *   R07 syncServer 404 → McpServerNotFoundError
 *   R08 syncServer 502 → McpServerUnreachableError
 *   R09 syncServer 429 → McpRateLimitedError
 *   R10 createServer 201 → Result.ok McpServer (has_credential false)
 *   R11 createServer 201 → Result.ok McpServer (has_credential true, api_key)
 *   R12 createServer 400 → McpEndpointNotAllowedError
 *   R13 createServer 422 → McpValidationError with fieldErrors map
 *   R14 createServer 429 → McpRateLimitedError
 *   R15 createServer 500 → McpServerError
 *   R16 createServer network failure → McpNetworkError
 *   R17 createServer 401 → McpAuthExpiredError
 *   R18 createServer 403 → McpForbiddenError
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
  McpValidationError,
  McpEndpointNotAllowedError,
} from "../data/errors";

// ---------------------------------------------------------------------------
// Mock authFetch
// ---------------------------------------------------------------------------

vi.mock("../../auth/data/httpClient", () => ({
  authFetch: vi.fn(),
}));

import { authFetch } from "../../auth/data/httpClient";
import { listServers, syncServer, createServer } from "../data/mcpRepository";

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

// ---------------------------------------------------------------------------
// Tests — createServer — §D-T004-TESTS-REPO
// ---------------------------------------------------------------------------

/** Fixture: minimal create request (auth.type = none, no credential) */
const CREATE_REQ_NONE = {
  name: "sandbox_writeonly",
  transport: "http" as const,
  endpoint: "http://localhost:8080/mcp",
  auth: { type: "none" as const, secret: null, refresh_token: null },
};

/** Fixture: create request with api_key auth */
const CREATE_REQ_API_KEY = {
  name: "sandbox_apikey",
  transport: "http" as const,
  endpoint: "https://api.example.com/mcp",
  auth: { type: "api_key" as const, secret: "vt-sandbox-key", refresh_token: null },
};

/** Fixture: 201 response body — no credential */
const MOCK_CREATED_SERVER_NONE = {
  id: "server-uuid-new",
  name: "sandbox_writeonly",
  transport: "http",
  endpoint: "http://localhost:8080/mcp",
  status: "draft",
  last_sync_at: null,
  created_by: "user-uuid",
  has_credential: false,
  auth_type: null,
};

/** Fixture: 201 response body — has_credential true */
const MOCK_CREATED_SERVER_APIKEY = {
  id: "server-uuid-apikey",
  name: "sandbox_apikey",
  transport: "http",
  endpoint: "https://api.example.com/mcp",
  status: "draft",
  last_sync_at: null,
  created_by: "user-uuid",
  has_credential: true,
  auth_type: "api_key",
};

describe("mcpRepository.createServer", () => {
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("R10 — 201 (auth=none) → Result.ok McpServer (has_credential=false)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(201, { data: MOCK_CREATED_SERVER_NONE, meta: { request_id: "r10" } }),
    );

    const result = await createServer(CREATE_REQ_NONE, onAuthFailure);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.id).toBe("server-uuid-new");
      expect(result.value.status).toBe("draft");
      expect(result.value.has_credential).toBe(false);
      expect(result.value.auth_type).toBeNull();
    }
  });

  it("R11 — 201 (auth=api_key) → Result.ok McpServer (has_credential=true)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(201, { data: MOCK_CREATED_SERVER_APIKEY, meta: { request_id: "r11" } }),
    );

    const result = await createServer(CREATE_REQ_API_KEY, onAuthFailure);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.has_credential).toBe(true);
      expect(result.value.auth_type).toBe("api_key");
      // Verify secret is NOT in the response value
      expect(result.value).not.toHaveProperty("secret");
    }
  });

  it("R12 — 400 → McpEndpointNotAllowedError (§D-T004-400-UNIT-ONLY)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(400, {
        data: null,
        meta: { request_id: "r12" },
        errors: [{ code: "MCP_ENDPOINT_NOT_ALLOWED", message: "Endpoint not allowed" }],
      }),
    );

    const result = await createServer(CREATE_REQ_NONE, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(McpEndpointNotAllowedError);
      expect(result.error.code).toBe("MCP_ENDPOINT_NOT_ALLOWED");
    }
  });

  it("R13 — 422 → McpValidationError with fieldErrors (§D-T004-422-PARSE)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(422, {
        detail: [
          { loc: ["body", "auth", "secret"], msg: "Field required", type: "missing" },
          { loc: ["body", "name"], msg: "ensure this value has at least 1 characters", type: "value_error" },
        ],
      }),
    );

    const result = await createServer(CREATE_REQ_NONE, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(McpValidationError);
      const validationErr = result.error as McpValidationError;
      expect(validationErr.code).toBe("MCP_VALIDATION_ERROR");
      expect(validationErr.fieldErrors["secret"]).toBe("Field required");
      expect(validationErr.fieldErrors["name"]).toBeDefined();
    }
  });

  it("R14 — 429 → McpRateLimitedError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(429, {}));

    const result = await createServer(CREATE_REQ_NONE, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(McpRateLimitedError);
      expect(result.error.code).toBe("MCP_RATE_LIMITED");
    }
  });

  it("R15 — 500 → McpServerError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(500, {}));

    const result = await createServer(CREATE_REQ_NONE, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(McpServerError);
      expect((result.error as McpServerError).status).toBe(500);
    }
  });

  it("R16 — network failure → McpNetworkError", async () => {
    mockAuthFetch.mockImplementationOnce(() => {
      return Promise.reject(new TypeError("Failed to fetch"));
    });

    const result = await createServer(CREATE_REQ_NONE, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(McpNetworkError);
      expect(result.error.code).toBe("MCP_NETWORK_ERROR");
    }
  });

  it("R17 — 401 → McpAuthExpiredError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(401, {}));

    const result = await createServer(CREATE_REQ_NONE, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(McpAuthExpiredError);
      expect(result.error.code).toBe("MCP_AUTH_EXPIRED");
    }
  });

  it("R18 — 403 → McpForbiddenError", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(403, {}));

    const result = await createServer(CREATE_REQ_NONE, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(McpForbiddenError);
      expect(result.error.code).toBe("MCP_FORBIDDEN");
    }
  });
});

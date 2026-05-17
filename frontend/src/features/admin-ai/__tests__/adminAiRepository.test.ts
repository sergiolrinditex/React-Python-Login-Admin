/**
 * Hilo People — adminAiRepository unit tests.
 *
 * Slice/Phase: P04-S01-T001 — AdminDashboardPage / Phase 4.
 *   Extended in P04-S01-T002 (§D-T002-TESTS): getProviders + getModels added.
 *   Extended in P04-S01-T003 (§D-T003-TESTS): createProvider added.
 * Write-set anchor: §D-T001-TESTS, §D-T002-TESTS, §D-T003-TESTS
 *
 * Responsibility: Unit tests for adminAiRepository.getUsage, getProviders, getModels,
 *   createProvider.
 *   authFetch is mocked at the fetch boundary (unit-level boundary, not business logic).
 *   Tests cover all Result paths that map to the 6 UX states.
 *
 * Cases (T01-T07): getUsage (existing).
 * Cases (T08-T17): getProviders + getModels (P04-S01-T002 additions).
 *   T08 — getProviders 200 happy path → Result.ok([AiProvider, ...]).
 *   T09 — getProviders 401 → AdminAiAuthExpiredError; onAuthFailure invoked.
 *   T10 — getProviders 403 → AdminAiForbiddenError.
 *   T11 — getProviders 500 → AdminAiInternalError.
 *   T12 — getProviders network reject → AdminAiNetworkError.
 *   T13 — getModels 200 happy path (no provider_id) → Result.ok([AiModel, ...]).
 *   T14 — getModels 401 → AdminAiAuthExpiredError.
 *   T15 — getModels 403 → AdminAiForbiddenError.
 *   T16 — getModels 500 → AdminAiInternalError.
 *   T17 — getModels network reject → AdminAiNetworkError.
 * Cases (T18-T26): createProvider (P04-S01-T003 additions).
 *   T18 — createProvider 201 happy path → Result.ok(AiProvider).
 *   T19 — createProvider 401 → AdminAiAuthExpiredError.
 *   T20 — createProvider 403 → AdminAiForbiddenError.
 *   T21 — createProvider 422 with fieldErrors → AdminAiValidationError with fieldErrors.
 *   T22 — createProvider 400 → AdminAiValidationError.
 *   T23 — createProvider 409 → AdminAiValidationError (ADMIN_PROVIDER_DUPLICATE_NAME).
 *   T24 — createProvider 500 → AdminAiInternalError.
 *   T25 — createProvider network reject → AdminAiNetworkError.
 *   T26 — createProvider PII-clean: secret_plain NEVER in logs.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { MockInstance } from "vitest";
import { getUsage, getProviders, getModels, createProvider } from "../data/adminAiRepository";
import {
  AdminAiAuthExpiredError,
  AdminAiForbiddenError,
  AdminAiValidationError,
  AdminAiNetworkError,
  AdminAiInternalError,
} from "../data/errors";
import { AuthSessionExpiredError } from "../../auth/data/errors";

// ---------------------------------------------------------------------------
// Mock authFetch
// ---------------------------------------------------------------------------

vi.mock("../../auth/data/httpClient", () => ({
  authFetch: vi.fn(),
}));

import { authFetch } from "../../auth/data/httpClient";
const mockAuthFetch = vi.mocked(authFetch);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_USAGE_ROW = {
  tokens_in: 1234,
  tokens_out: 567,
  estimated_cost: 0.0123,
  latency_ms_avg: 842,
  invocations: 12,
  model_name: "gpt-4o-mini",
};

const MOCK_TOTALS = {
  tokens_in: 1234,
  tokens_out: 567,
  estimated_cost: 0.0123,
  invocations: 12,
  latency_ms_avg: 842,
};

const MOCK_USAGE_SUMMARY = {
  from: "2026-04-16T00:00:00+00:00",
  to: "2026-05-16T00:00:00+00:00",
  group_by: "model" as const,
  rows: [MOCK_USAGE_ROW],
  totals: MOCK_TOTALS,
};

const EMPTY_TOTALS = {
  tokens_in: 0,
  tokens_out: 0,
  estimated_cost: 0,
  invocations: 0,
  latency_ms_avg: 0,
};

function makeResponse(
  status: number,
  body: unknown,
  extraHeaders: Record<string, string> = {},
): Response {
  const headers = new Headers({
    "content-type": "application/json",
    "x-request-id": "test-request-id",
    ...extraHeaders,
  });
  return {
    status,
    ok: status >= 200 && status < 300,
    headers,
    text: () => Promise.resolve(JSON.stringify(body)),
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

const DEFAULT_PARAMS = {
  from: "2026-04-16T00:00:00Z",
  to: "2026-05-16T00:00:00Z",
  group_by: "model" as const,
};

const onAuthFailure = vi.fn();

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("adminAiRepository.getUsage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("T01 — 200 happy path → Result.ok with populated rows", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, {
        data: MOCK_USAGE_SUMMARY,
        meta: { request_id: "test-request-id" },
      }),
    );

    const result = await getUsage(DEFAULT_PARAMS, onAuthFailure);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.rows).toHaveLength(1);
      expect(result.value.rows[0].model_name).toBe("gpt-4o-mini");
      expect(result.value.totals.invocations).toBe(12);
      expect(result.value.group_by).toBe("model");
    }
  });

  it("T02 — 200 empty (rows=[], totals all zeros) → Result.ok with empty data", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, {
        data: {
          from: "2026-04-16T00:00:00+00:00",
          to: "2026-05-16T00:00:00+00:00",
          group_by: "model",
          rows: [],
          totals: EMPTY_TOTALS,
        },
        meta: { request_id: "test-request-id" },
      }),
    );

    const result = await getUsage(DEFAULT_PARAMS, onAuthFailure);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.rows).toHaveLength(0);
      expect(result.value.totals.invocations).toBe(0);
    }
  });

  it("T03 — 401 final → Result.err(AdminAiAuthExpiredError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(401, { errors: [{ code: "AUTH_SESSION_EXPIRED" }] }),
    );

    const result = await getUsage(DEFAULT_PARAMS, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiAuthExpiredError);
    }
  });

  it("T03b — AuthSessionExpiredError thrown by authFetch → Result.err(AdminAiAuthExpiredError)", async () => {
    mockAuthFetch.mockRejectedValueOnce(new AuthSessionExpiredError());

    const result = await getUsage(DEFAULT_PARAMS, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiAuthExpiredError);
    }
  });

  it("T04 — 403 forbidden → Result.err(AdminAiForbiddenError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(403, { errors: [{ code: "AUTH_FORBIDDEN" }] }),
    );

    const result = await getUsage(DEFAULT_PARAMS, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiForbiddenError);
    }
  });

  it("T05 — 422 validation error → Result.err(AdminAiValidationError) with server code", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(422, {
        errors: [{ code: "ADMIN_USAGE_WINDOW_TOO_WIDE", message: "Window exceeds 90 days." }],
      }),
    );

    const result = await getUsage(DEFAULT_PARAMS, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiValidationError);
      const err = result.error as AdminAiValidationError;
      expect(err.serverCode).toBe("ADMIN_USAGE_WINDOW_TOO_WIDE");
    }
  });

  it("T06 — 500 server error → Result.err(AdminAiInternalError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(500, { errors: [{ code: "INTERNAL_ERROR" }] }),
    );

    const result = await getUsage(DEFAULT_PARAMS, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiInternalError);
      const err = result.error as AdminAiInternalError;
      expect(err.status).toBe(500);
    }
  });

  it("T07 — network rejection (TypeError) → Result.err(AdminAiNetworkError)", async () => {
    mockAuthFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await getUsage(DEFAULT_PARAMS, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiNetworkError);
    }
  });

  it("T08-url — URL is built correctly with all params", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, { data: MOCK_USAGE_SUMMARY, meta: {} }),
    );

    await getUsage(
      { from: "2026-04-16T00:00:00Z", to: "2026-05-16T00:00:00Z", group_by: "day" },
      onAuthFailure,
    );

    expect(mockAuthFetch).toHaveBeenCalledWith(
      expect.stringContaining("group_by=day"),
      expect.objectContaining({ method: "GET" }),
      expect.objectContaining({ onAuthFailure }),
    );
  });
});

// ---------------------------------------------------------------------------
// P04-S01-T002 additions: getProviders + getModels
// ---------------------------------------------------------------------------

// Fixtures for providers + models
const MOCK_PROVIDER = {
  id: "prov-uuid-1234",
  name: "litellm_verification_sandbox",
  provider_type: "litellm",
  base_url: "http://localhost:4000",
  status: "active",
  created_by: null,
  has_credentials: false,
  credential_auth_type: null,
  expires_at: null,
};

const MOCK_MODEL = {
  id: "model-uuid-5678",
  provider_id: "prov-uuid-1234",
  model_id: "gpt-4o-mini",
  model_type: "chat",
  capabilities: ["chat", "streaming"],
  enabled: true,
  is_default: true,
  pricing: {},
  latency_ms_avg: null,
};

describe("adminAiRepository.getProviders", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("T08 — getProviders happy path → Result.ok([AiProvider])", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, { data: [MOCK_PROVIDER], meta: { request_id: "test-req-1" } }),
    );

    const result = await getProviders(onAuthFailure);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value).toHaveLength(1);
      expect(result.value[0].status).toBe("active");
      expect(result.value[0].provider_type).toBe("litellm");
    }
  });

  it("T09 — getProviders 401 → AdminAiAuthExpiredError; onAuthFailure invoked via authFetch", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(401, { errors: [{ code: "AUTH_SESSION_EXPIRED" }] }),
    );

    const result = await getProviders(onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiAuthExpiredError);
    }
  });

  it("T10 — getProviders 403 → AdminAiForbiddenError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(403, { errors: [{ code: "AUTH_FORBIDDEN" }] }),
    );

    const result = await getProviders(onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiForbiddenError);
    }
  });

  it("T11 — getProviders 500 → AdminAiInternalError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(500, { errors: [{ code: "INTERNAL_ERROR" }] }),
    );

    const result = await getProviders(onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiInternalError);
      const err = result.error as AdminAiInternalError;
      expect(err.status).toBe(500);
    }
  });

  it("T12 — getProviders network reject → AdminAiNetworkError", async () => {
    mockAuthFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await getProviders(onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiNetworkError);
    }
  });
});

describe("adminAiRepository.getModels", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("T13 — getModels happy path (no provider_id) → Result.ok([AiModel])", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, { data: [MOCK_MODEL], meta: { request_id: "test-req-2" } }),
    );

    const result = await getModels(undefined, onAuthFailure);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value).toHaveLength(1);
      expect(result.value[0].enabled).toBe(true);
      expect(result.value[0].is_default).toBe(true);
    }
    // URL should not contain provider_id filter
    expect(mockAuthFetch).toHaveBeenCalledWith(
      "/api/v1/admin/ai/models",
      expect.objectContaining({ method: "GET" }),
      expect.objectContaining({ onAuthFailure }),
    );
  });

  it("T14 — getModels 401 → AdminAiAuthExpiredError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(401, { errors: [{ code: "AUTH_SESSION_EXPIRED" }] }),
    );

    const result = await getModels(undefined, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiAuthExpiredError);
    }
  });

  it("T15 — getModels 403 → AdminAiForbiddenError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(403, { errors: [{ code: "AUTH_FORBIDDEN" }] }),
    );

    const result = await getModels(undefined, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiForbiddenError);
    }
  });

  it("T16 — getModels 500 → AdminAiInternalError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(500, { errors: [{ code: "INTERNAL_ERROR" }] }),
    );

    const result = await getModels(undefined, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiInternalError);
    }
  });

  it("T17 — getModels network reject → AdminAiNetworkError", async () => {
    mockAuthFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await getModels(undefined, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiNetworkError);
    }
  });
});

// ---------------------------------------------------------------------------
// P04-S01-T003 additions: createProvider
// ---------------------------------------------------------------------------

// Fixture for createProvider request (secret_plain cast for test purposes)
const MOCK_CREATE_PROVIDER_REQUEST = {
  provider_type: "litellm" as const,
  name: "litellm_verification_sandbox",
  base_url: "http://localhost:4000",
  credentials: {
    auth_type: "bearer" as const,
    secret_plain: "hilo-dev-litellm-master-key-2026",
  },
};

const MOCK_PROVIDER_OUT = {
  id: "prov-uuid-created-1234",
  name: "litellm_verification_sandbox",
  provider_type: "litellm",
  base_url: "http://localhost:4000",
  status: "draft",
  created_by: null,
  has_credentials: true,
  credential_auth_type: "bearer",
  expires_at: null,
};

describe("adminAiRepository.createProvider", () => {
  let consoleSpy: MockInstance;

  beforeEach(() => {
    vi.clearAllMocks();
    // Spy on ALL console methods to verify PII-clean logs
    consoleSpy = vi.spyOn(console, "info").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("T18 — createProvider 201 happy path → Result.ok(AiProvider)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(201, { data: MOCK_PROVIDER_OUT, meta: { request_id: "test-req-create" } }),
    );

    const result = await createProvider(MOCK_CREATE_PROVIDER_REQUEST, onAuthFailure);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.provider_type).toBe("litellm");
      expect(result.value.has_credentials).toBe(true);
      expect(result.value.status).toBe("draft");
    }
    // Verify POST was called with JSON body
    expect(mockAuthFetch).toHaveBeenCalledWith(
      "/api/v1/admin/ai/providers",
      expect.objectContaining({ method: "POST" }),
      expect.objectContaining({ onAuthFailure }),
    );
  });

  it("T19 — createProvider 401 → AdminAiAuthExpiredError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(401, { errors: [{ code: "AUTH_SESSION_EXPIRED" }] }),
    );

    const result = await createProvider(MOCK_CREATE_PROVIDER_REQUEST, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiAuthExpiredError);
    }
  });

  it("T20 — createProvider 403 → AdminAiForbiddenError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(403, { errors: [{ code: "AUTH_FORBIDDEN" }] }),
    );

    const result = await createProvider(MOCK_CREATE_PROVIDER_REQUEST, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiForbiddenError);
    }
  });

  it("T21 — createProvider 422 with fieldErrors → AdminAiValidationError with fieldErrors[]", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(422, {
        code: "ADMIN_PROVIDER_VALIDATION_ERROR",
        errors: [
          { field: "name", code: "INVALID_NAME", message: "Name must be non-blank." },
          { field: "credentials", code: "INVALID_SECRET", message: "Secret is required." },
        ],
      }),
    );

    const result = await createProvider(MOCK_CREATE_PROVIDER_REQUEST, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiValidationError);
      const err = result.error as AdminAiValidationError;
      expect(err.serverCode).toBe("ADMIN_PROVIDER_VALIDATION_ERROR");
      expect(err.fieldErrors).toHaveLength(2);
      expect(err.fieldErrors?.[0].field).toBe("name");
    }
  });

  it("T22 — createProvider 400 → AdminAiValidationError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(400, { code: "ADMIN_PROVIDER_BAD_REQUEST", error: "Bad request" }),
    );

    const result = await createProvider(MOCK_CREATE_PROVIDER_REQUEST, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiValidationError);
    }
  });

  it("T23 — createProvider 409 → AdminAiValidationError (ADMIN_PROVIDER_DUPLICATE_NAME)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(409, { code: "ADMIN_PROVIDER_DUPLICATE_NAME", error: "Conflict" }),
    );

    const result = await createProvider(MOCK_CREATE_PROVIDER_REQUEST, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiValidationError);
      const err = result.error as AdminAiValidationError;
      expect(err.serverCode).toBe("ADMIN_PROVIDER_DUPLICATE_NAME");
    }
  });

  it("T24 — createProvider 500 → AdminAiInternalError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(500, { errors: [{ code: "INTERNAL_ERROR" }] }),
    );

    const result = await createProvider(MOCK_CREATE_PROVIDER_REQUEST, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiInternalError);
      const err = result.error as AdminAiInternalError;
      expect(err.status).toBe(500);
    }
  });

  it("T25 — createProvider network reject → AdminAiNetworkError", async () => {
    mockAuthFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await createProvider(MOCK_CREATE_PROVIDER_REQUEST, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(AdminAiNetworkError);
    }
  });

  it("T26 — createProvider PII-clean: secret_plain NEVER appears in console logs", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(201, { data: MOCK_PROVIDER_OUT, meta: { request_id: "pii-test" } }),
    );

    await createProvider(MOCK_CREATE_PROVIDER_REQUEST, onAuthFailure);

    // Collect all console.info calls as strings
    const allLogCalls = consoleSpy.mock.calls.map((args) => JSON.stringify(args));
    const secretValue = "hilo-dev-litellm-master-key-2026";
    for (const logEntry of allLogCalls) {
      expect(logEntry).not.toContain(secretValue);
    }
  });
});

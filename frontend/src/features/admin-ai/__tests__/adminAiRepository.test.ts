/**
 * Hilo People — adminAiRepository unit tests.
 *
 * Slice/Phase: P04-S01-T001 — AdminDashboardPage / Phase 4.
 * Write-set anchor: §D-T001-TESTS
 *
 * Responsibility: Unit tests for adminAiRepository.getUsage.
 *   authFetch is mocked at the fetch boundary (unit-level boundary, not business logic).
 *   Tests cover all 7 Result paths that map to the 5 UX states.
 *
 * Cases:
 *   T01 — 200 happy path → Result.ok(UsageSummary) with populated rows.
 *   T02 — 200 empty (rows=[], totals all zeros) → Result.ok, empty UX state.
 *   T03 — 401 final (authFetch exhausted) → Result.err(AdminAiAuthExpiredError).
 *   T04 — 403 forbidden → Result.err(AdminAiForbiddenError).
 *   T05 — 422 validation error → Result.err(AdminAiValidationError) with server code.
 *   T06 — 500 server error → Result.err(AdminAiInternalError).
 *   T07 — network rejection → Result.err(AdminAiNetworkError).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { getUsage } from "../data/adminAiRepository";
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

  it("T08 — URL is built correctly with all params", async () => {
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

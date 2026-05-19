/**
 * Hilo People — usageRepository unit tests.
 *
 * Slice/Phase: P04-S03-T002 — UsagePage / Phase 4 Complete Features.
 *
 * Responsibility: Tests for getUsage in admin/data/usageRepository.ts.
 *   Covers happy path, all error paths, and abort signal handling.
 *   Mocks only authFetch (auth layer we control via boundary).
 *   7 tests total:
 *     - 200 happy path (returns Result.ok with UsageSummary)
 *     - 422 validation error
 *     - 403 forbidden
 *     - 401 auth expired
 *     - 5xx server error
 *     - network error (fetch throws)
 *     - abort signal handling
 *
 * Non-negotiables: tests are REAL in that they call actual getUsage logic;
 *   only authFetch is mocked (external boundary we do not control in unit tests).
 *
 * D-T002-TEST-REPO: Canonical write_set anchor for this file.
 * Source ref: §D-T002-TEST-REPO, task pack §12 AC1–AC9.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { getUsage } from "../usageRepository";
import {
  UsageValidationError,
  UsageForbiddenError,
  UsageAuthExpiredError,
  UsageNetworkError,
  UsageServerError,
} from "../errors";
import type { UsageSummary } from "../../domain/types";

// ---------------------------------------------------------------------------
// Mock authFetch
// ---------------------------------------------------------------------------

vi.mock("../../../auth/data/httpClient", () => ({
  authFetch: vi.fn(),
}));

import { authFetch } from "../../../auth/data/httpClient";

const mockAuthFetch = authFetch as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEFAULT_QUERY = {
  from: new Date("2026-04-16T00:00:00Z"),
  to: new Date("2026-05-16T00:00:00Z"),
  groupBy: "model_day" as const,
};

const MOCK_SUMMARY: UsageSummary = {
  from: "2026-04-16T00:00:00+00:00",
  to: "2026-05-16T00:00:00+00:00",
  group_by: "model_day",
  rows: [
    {
      model_id: "uuid-model-1",
      model_name: "gpt-4o",
      provider_type: "openai",
      day: "2026-05-15",
      tokens_in: 1000,
      tokens_out: 500,
      estimated_cost: 0.025,
      latency_ms_avg: 1200,
      invocations: 5,
    },
  ],
  totals: {
    tokens_in: 1000,
    tokens_out: 500,
    estimated_cost: 0.025,
    latency_ms_avg: 1200,
    invocations: 5,
  },
};

function makeResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  const responseHeaders = new Headers({ "content-type": "application/json", ...headers });
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: responseHeaders,
    text: async () => JSON.stringify(body),
    json: async () => body,
  } as unknown as Response;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("usageRepository.getUsage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("usageRepository: 200 returns Result.ok with UsageSummary", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, { data: MOCK_SUMMARY }, { "x-request-id": "req-001" }),
    );

    const result = await getUsage(DEFAULT_QUERY);

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("Expected ok");
    expect(result.value.rows).toHaveLength(1);
    expect(result.value.rows[0].model_name).toBe("gpt-4o");
    expect(result.value.totals.invocations).toBe(5);
  });

  it("usageRepository: 200 with empty rows returns Result.ok with empty rows", async () => {
    const emptySummary: UsageSummary = {
      ...MOCK_SUMMARY,
      rows: [],
      totals: { tokens_in: 0, tokens_out: 0, estimated_cost: 0, latency_ms_avg: null, invocations: 0 },
    };
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, { data: emptySummary }),
    );

    const result = await getUsage(DEFAULT_QUERY);

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("Expected ok");
    expect(result.value.rows).toHaveLength(0);
  });

  it("usageRepository: 422 returns UsageValidationError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(422, { errors: [{ code: "ADMIN_USAGE_INVALID_PAYLOAD", message: "Invalid params." }] }),
    );

    const result = await getUsage(DEFAULT_QUERY);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("Expected error");
    expect(result.error).toBeInstanceOf(UsageValidationError);
    expect(result.error.code).toBe("USAGE_VALIDATION_ERROR");
  });

  it("usageRepository: 403 returns UsageForbiddenError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(403, { errors: [{ code: "AUTH_FORBIDDEN", message: "Forbidden." }] }),
    );

    const result = await getUsage(DEFAULT_QUERY);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("Expected error");
    expect(result.error).toBeInstanceOf(UsageForbiddenError);
    expect(result.error.code).toBe("USAGE_FORBIDDEN");
  });

  it("usageRepository: 401 returns UsageAuthExpiredError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(401, { errors: [{ code: "AUTH_SESSION_EXPIRED", message: "Expired." }] }),
    );

    const result = await getUsage(DEFAULT_QUERY);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("Expected error");
    expect(result.error).toBeInstanceOf(UsageAuthExpiredError);
    expect(result.error.code).toBe("USAGE_AUTH_EXPIRED");
  });

  it("usageRepository: 500 returns UsageServerError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(500, { errors: [{ code: "INTERNAL_ERROR", message: "Server error." }] }),
    );

    const result = await getUsage(DEFAULT_QUERY);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("Expected error");
    expect(result.error).toBeInstanceOf(UsageServerError);
    expect(result.error.code).toBe("USAGE_SERVER_ERROR");
    expect((result.error as UsageServerError).status).toBe(500);
  });

  it("usageRepository: network error (fetch throws TypeError) returns UsageNetworkError", async () => {
    mockAuthFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await getUsage(DEFAULT_QUERY);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("Expected error");
    expect(result.error).toBeInstanceOf(UsageNetworkError);
    expect(result.error.code).toBe("USAGE_NETWORK_ERROR");
  });

  it("usageRepository: AbortError returns UsageNetworkError (aborted)", async () => {
    const abortError = new DOMException("The operation was aborted.", "AbortError");
    mockAuthFetch.mockRejectedValueOnce(abortError);

    const controller = new AbortController();
    controller.abort();

    const result = await getUsage(DEFAULT_QUERY, undefined, controller.signal);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("Expected error");
    expect(result.error).toBeInstanceOf(UsageNetworkError);
    expect(result.error.message).toContain("aborted");
  });
});

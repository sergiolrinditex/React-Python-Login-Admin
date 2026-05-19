/**
 * Hilo People — auditRepository unit tests.
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: Tests for getAuditPage in audit/data/auditRepository.ts.
 *   Covers happy path, all error paths, abort signal handling, and PII-clean logging.
 *   Mocks only authFetch (auth layer we control via boundary).
 *   8 tests total:
 *     - 200 happy path (returns Result.ok with AuditPage)
 *     - 200 with empty rows
 *     - 401 → AuditAuthExpiredError
 *     - 403 → AuditForbiddenError
 *     - 422 → AuditValidationError
 *     - 5xx → AuditServerError
 *     - network error (fetch throws) → AuditNetworkError
 *     - abort signal → AuditNetworkError (aborted)
 *
 * Non-negotiables: tests are REAL for actual getAuditPage logic;
 *   only authFetch is mocked (external boundary).
 *
 * §D-T001-TESTS: Canonical write_set anchor for this file.
 * Source ref: §D-T001-TESTS, task pack §16 AC6.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { getAuditPage } from "../auditRepository";
import {
  AuditValidationError,
  AuditForbiddenError,
  AuditAuthExpiredError,
  AuditNetworkError,
  AuditServerError,
} from "../errors";
import type { AuditPage } from "../../domain/types";

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
  from: new Date("2026-05-12T00:00:00Z"),
  to: new Date("2026-05-19T23:59:59Z"),
};

const MOCK_AUDIT_PAGE: AuditPage = {
  rows: [
    {
      id: "audit-row-1",
      actor_user_id: "actor-uuid-1234",
      action: "auth.sign_in",
      entity_type: "user",
      entity_id: "user-uuid-5678",
      metadata: { request_id: "req-abc123", ip: "10.0.0.1" }, // IP in metadata — must NOT be logged
      created_at: "2026-05-19T10:00:00Z",
    },
  ],
  next_cursor: null,
  has_more: false,
  count: 1,
};

const MOCK_BACKEND_RESPONSE = {
  data: MOCK_AUDIT_PAGE.rows,
  meta: {
    request_id: "server-req-id-001",
    next_cursor: null,
    has_more: false,
    count: 1,
  },
  errors: [],
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

describe("auditRepository.getAuditPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("auditRepository: 200 returns Result.ok with AuditPage", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, MOCK_BACKEND_RESPONSE, { "x-request-id": "req-001" }),
    );

    const result = await getAuditPage(DEFAULT_QUERY);

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("Expected ok");
    expect(result.value.rows).toHaveLength(1);
    expect(result.value.rows[0].action).toBe("auth.sign_in");
    expect(result.value.has_more).toBe(false);
    expect(result.value.next_cursor).toBeNull();
    expect(result.value.count).toBe(1);
  });

  it("auditRepository: 200 with empty rows returns Result.ok with empty rows", async () => {
    const emptyResponse = {
      data: [],
      meta: { request_id: "req-002", next_cursor: null, has_more: false, count: 0 },
      errors: [],
    };
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, emptyResponse),
    );

    const result = await getAuditPage(DEFAULT_QUERY);

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("Expected ok");
    expect(result.value.rows).toHaveLength(0);
    expect(result.value.count).toBe(0);
  });

  it("auditRepository: 401 returns AuditAuthExpiredError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(401, { errors: [{ code: "AUTH_SESSION_EXPIRED", message: "Expired." }] }),
    );

    const result = await getAuditPage(DEFAULT_QUERY);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("Expected error");
    expect(result.error).toBeInstanceOf(AuditAuthExpiredError);
    expect(result.error.code).toBe("AUDIT_AUTH_EXPIRED");
  });

  it("auditRepository: 403 returns AuditForbiddenError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(403, { errors: [{ code: "AUTH_FORBIDDEN", message: "Forbidden." }] }),
    );

    const result = await getAuditPage(DEFAULT_QUERY);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("Expected error");
    expect(result.error).toBeInstanceOf(AuditForbiddenError);
    expect(result.error.code).toBe("AUDIT_FORBIDDEN");
  });

  it("auditRepository: 422 returns AuditValidationError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(422, { errors: [{ code: "AUDIT_WINDOW_INVALID", message: "Invalid window." }] }),
    );

    const result = await getAuditPage(DEFAULT_QUERY);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("Expected error");
    expect(result.error).toBeInstanceOf(AuditValidationError);
    expect(result.error.code).toBe("AUDIT_VALIDATION_ERROR");
  });

  it("auditRepository: 500 returns AuditServerError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(500, { errors: [{ code: "INTERNAL_ERROR", message: "Server error." }] }),
    );

    const result = await getAuditPage(DEFAULT_QUERY);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("Expected error");
    expect(result.error).toBeInstanceOf(AuditServerError);
    expect(result.error.code).toBe("AUDIT_SERVER_ERROR");
    expect((result.error as AuditServerError).status).toBe(500);
  });

  it("auditRepository: network error (fetch throws TypeError) returns AuditNetworkError", async () => {
    mockAuthFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await getAuditPage(DEFAULT_QUERY);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("Expected error");
    expect(result.error).toBeInstanceOf(AuditNetworkError);
    expect(result.error.code).toBe("AUDIT_NETWORK_ERROR");
  });

  it("auditRepository: AbortError returns AuditNetworkError (aborted)", async () => {
    const abortError = new DOMException("The operation was aborted.", "AbortError");
    mockAuthFetch.mockRejectedValueOnce(abortError);

    const controller = new AbortController();
    controller.abort();

    const result = await getAuditPage(DEFAULT_QUERY, undefined, controller.signal);

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("Expected error");
    expect(result.error).toBeInstanceOf(AuditNetworkError);
    expect(result.error.message).toContain("aborted");
  });

  it("auditRepository: PII-clean — logger spy does not receive full rows, actor UUID, or IP", async () => {
    // Spy on console.info — test runs with VITE_ENABLE_VERBOSE_LOGGING=true from the runner
    // so logVerbose calls will fire. We verify no PII leaks into any log argument.
    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => void 0);

    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, MOCK_BACKEND_RESPONSE, { "x-request-id": "req-pii-test" }),
    );

    await getAuditPage({
      ...DEFAULT_QUERY,
      actor: "actor-uuid-1234",
      action: "auth.sign_in",
    });

    // Verify no log call includes full actor UUID or IP
    for (const call of infoSpy.mock.calls) {
      const logArg = JSON.stringify(call);
      // Actor UUID should never be fully logged (BEFORE log uses has_actor_present, not the UUID)
      expect(logArg).not.toContain("actor-uuid-1234");
      // IP from metadata must never appear in logs
      expect(logArg).not.toContain("10.0.0.1");
      // Full rows must never appear
      expect(logArg).not.toContain("audit-row-1");
    }

    infoSpy.mockRestore();
  });
});

/**
 * Hilo People — UserRepository unit tests.
 *
 * Slice/Phase: P03-S02-T004 — AccountPage / Phase 3.
 *
 * Responsibility: Tests for data/userRepository.ts — HTTP adapter for
 *   GET /api/v1/users/me and PATCH /api/v1/users/me/language.
 *   Mocks ONLY the HTTP layer (authFetch) — all domain logic is real.
 *
 * Test cases (≥8):
 *   T01 — getMe 200 → Result.ok(UserProfile)
 *   T02 — getMe 401 → Result.err(UserAuthExpiredError)
 *   T03 — getMe 5xx → Result.err(UserServerError)
 *   T04 — getMe network fail → Result.err(UserNetworkError)
 *   T05 — updateLanguage 200 (full body) → Result.ok with preferred_language updated
 *   T06 — updateLanguage 400 → Result.err(UserValidationError)
 *   T07 — updateLanguage 401 → Result.err(UserAuthExpiredError)
 *   T08 — updateLanguage 5xx → Result.err(UserServerError)
 *   T09 — updateLanguage 403 → Result.err(UserForbiddenError)
 *   T10 — getMe network error (TypeError) → Result.err(UserNetworkError)
 *   T11 — verbose logging: BEFORE+AFTER+ERROR logs present
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { UserRepository } from "../data/userRepository";
import {
  UserValidationError,
  UserAuthExpiredError,
  UserForbiddenError,
  UserNetworkError,
  UserServerError,
} from "../domain/types";
import type { UserProfile } from "../domain/types";

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

const MOCK_PROFILE: UserProfile = {
  id: "7b34e2ca-a9cc-4152-9be0-552d200464ce",
  email: "employee.verification@inditex-sandbox.com",
  full_name: "Elena Verificación",
  status: "active",
  preferred_language: "es",
  roles: ["employee"],
  employee_profile: {
    employee_id: "EMP-VERIFY-001",
    brand: "Zara",
    society: "ITX-ES",
    center: "Madrid-HQ",
    country: "ES",
    department: "People & Talent",
  },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

// Helper: create a mock Response
function mockResponse(status: number, body?: unknown): Response {
  const text = body !== undefined ? JSON.stringify(body) : "";
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: new Headers({ "x-request-id": "test-request-id" }),
    text: () => Promise.resolve(text),
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("UserRepository", () => {
  let repo: UserRepository;

  beforeEach(() => {
    repo = new UserRepository();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // T01
  it("T01 — getMe 200 → Result.ok(UserProfile) with full shape", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      mockResponse(200, { data: MOCK_PROFILE }),
    );

    const result = await repo.getMe();

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.id).toBe(MOCK_PROFILE.id);
      expect(result.value.preferred_language).toBe("es");
      expect(result.value.employee_profile?.employee_id).toBe("EMP-VERIFY-001");
    }
  });

  // T02
  it("T02 — getMe 401 → Result.err(UserAuthExpiredError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(mockResponse(401));

    const result = await repo.getMe();

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(UserAuthExpiredError);
      expect(result.error.code).toBe("USER_AUTH_EXPIRED");
    }
  });

  // T03
  it("T03 — getMe 500 → Result.err(UserServerError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(mockResponse(500));

    const result = await repo.getMe();

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(UserServerError);
      expect(result.error.code).toBe("USER_SERVER_ERROR");
      expect((result.error as UserServerError).status).toBe(500);
    }
  });

  // T04
  it("T04 — getMe network failure (fetch throws) → Result.err(UserNetworkError)", async () => {
    mockAuthFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await repo.getMe();

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(UserNetworkError);
      expect(result.error.code).toBe("USER_NETWORK_ERROR");
    }
  });

  // T05
  it("T05 — updateLanguage('en') 200 → Result.ok(profile with preferred_language=en)", async () => {
    const updatedProfile = { ...MOCK_PROFILE, preferred_language: "en" as const };
    mockAuthFetch.mockResolvedValueOnce(
      mockResponse(200, { data: updatedProfile }),
    );

    const result = await repo.updateLanguage("en");

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.preferred_language).toBe("en");
      expect(result.value.id).toBe(MOCK_PROFILE.id);
    }
  });

  // T06
  it("T06 — updateLanguage 400 → Result.err(UserValidationError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(mockResponse(400));

    const result = await repo.updateLanguage("fr");

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(UserValidationError);
      expect(result.error.code).toBe("USER_VALIDATION_ERROR");
    }
  });

  // T07
  it("T07 — updateLanguage 401 → Result.err(UserAuthExpiredError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(mockResponse(401));

    const result = await repo.updateLanguage("en");

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(UserAuthExpiredError);
    }
  });

  // T08
  it("T08 — updateLanguage 503 → Result.err(UserServerError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(mockResponse(503));

    const result = await repo.updateLanguage("en");

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(UserServerError);
      expect((result.error as UserServerError).status).toBe(503);
    }
  });

  // T09
  it("T09 — updateLanguage 403 → Result.err(UserForbiddenError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(mockResponse(403));

    const result = await repo.updateLanguage("fr");

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(UserForbiddenError);
      expect(result.error.code).toBe("USER_FORBIDDEN");
    }
  });

  // T10
  it("T10 — getMe generic Error → Result.err(UserNetworkError)", async () => {
    mockAuthFetch.mockRejectedValueOnce(new Error("Connection refused"));

    const result = await repo.getMe();

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(UserNetworkError);
    }
  });

  // T11
  it("T11 — updateLanguage 422 treated as 400 validation error", async () => {
    mockAuthFetch.mockResolvedValueOnce(mockResponse(422));

    const result = await repo.updateLanguage("en");

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(UserValidationError);
    }
  });

  // T12
  it("T12 — getMe 403 → Result.err(UserForbiddenError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(mockResponse(403));

    const result = await repo.getMe();

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(UserForbiddenError);
    }
  });
});

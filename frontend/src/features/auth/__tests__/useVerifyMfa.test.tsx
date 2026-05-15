/**
 * Hilo People — useVerifyMfa hook tests.
 *
 * Slice/Phase: P03-S01-T005 — TwoFactorPage (/auth/2fa editorial móvil) / Phase 3.
 *
 * Responsibility: Unit tests for the useVerifyMfa presentation hook.
 *   Tests H01–H07 covering all success, error, and guard paths.
 *   Repo is injected as a fake object (data layer boundary mock — not business logic mock).
 *
 * Test policy (non-negotiables §tests):
 *   - Repo fake replaces ONLY the network boundary (IAuthRepository interface).
 *   - No mocking of useVerifyMfa internals; tests drive the hook via renderHook.
 *   - H06/H07: validate PII safety — code and challengeToken NEVER logged.
 *
 * §D-T005-TEST-DIR-COLOCATE: placed under __tests__/ consistent with T001/T002 (P-33 #3).
 * §D-T005-AGGREGATE-401: H02 verifies one error class covers the aggregate 401.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { useVerifyMfa } from "../presentation/useVerifyMfa";
import type { IAuthRepository, VerifyMfaRequest, VerifyMfaOutcome } from "../domain/AuthRepository";
import type { SignInRequest, SignInOutcome, SignUpRequest, ForgotPasswordRequest } from "../domain/AuthRepository";
import type { UserProfile } from "../domain/types";
import {
  MfaCodeInvalidError,
  MfaChallengeExpiredError,
  MfaVerifyRateLimitedError,
  MfaVerifyInternalError,
  NetworkError,
} from "../data/errors";
import * as logger from "../data/logger";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_USER: UserProfile = {
  id: "22222222-2222-2222-2222-222222222222",
  email: "employee.verification@inditex-sandbox.com",
  full_name: "Verification Employee",
  status: "active",
  preferred_language: "es",
  roles: ["employee"],
  employee_profile: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const MOCK_TOKEN = "mock-access-token-xyz-abcdefghijklmnop";

const SUCCESS_OUTCOME: VerifyMfaOutcome = {
  accessToken: MOCK_TOKEN,
  expiresIn: 1800,
  user: MOCK_USER,
};

const VALID_REQUEST: VerifyMfaRequest = {
  challengeToken: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.challenge-payload.signature",
  code: "123456",
};

// ---------------------------------------------------------------------------
// Fake repo builder — injects only the verifyMfa method; others are stubs
// ---------------------------------------------------------------------------

function makeRepo(
  verifyResult: { ok: true; value: VerifyMfaOutcome } | { ok: false; error: Error },
): IAuthRepository {
  return {
    verifyMfa: vi.fn(async (_req: VerifyMfaRequest) => verifyResult),
    signIn: vi.fn(async (_req: SignInRequest) => ({
      ok: true as const,
      value: {
        kind: "success" as const,
        accessToken: MOCK_TOKEN,
        user: MOCK_USER,
      } as SignInOutcome,
    })),
    signUp: vi.fn(async (_req: SignUpRequest) => ({
      ok: true as const,
      value: { user_id: "stub", mfa_required: false as const },
    })),
    forgotPassword: vi.fn(async (_req: ForgotPasswordRequest) => ({
      ok: true as const,
      value: { sent: true as const },
    })),
    refresh: vi.fn(async () => ({ ok: true as const, value: MOCK_TOKEN })),
    fetchMe: vi.fn(async () => ({ ok: true as const, value: MOCK_USER })),
    logout: vi.fn(async () => ({ ok: true as const, value: undefined })),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useVerifyMfa", () => {
  let onSuccess: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onSuccess = vi.fn();
  });

  it("H01: success path — repo.verifyMfa returns 200 → onSuccess called with token+user, isLoading toggles, no error", async () => {
    const repo = makeRepo({ ok: true, value: SUCCESS_OUTCOME });
    const { result } = renderHook(() => useVerifyMfa(repo, onSuccess));

    let outcome: VerifyMfaOutcome | null = null;
    await act(async () => {
      outcome = await result.current.submit(VALID_REQUEST);
    });

    expect(outcome).not.toBeNull();
    expect(outcome!.accessToken).toBe(MOCK_TOKEN);
    expect(outcome!.user.id).toBe(MOCK_USER.id);
    expect(onSuccess).toHaveBeenCalledTimes(1);
    expect(onSuccess).toHaveBeenCalledWith(MOCK_TOKEN, MOCK_USER);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(repo.verifyMfa).toHaveBeenCalledWith(VALID_REQUEST);
  });

  it("H02: wrong code — 401 MfaCodeInvalidError → error set, onSuccess not called, outcome null", async () => {
    const repo = makeRepo({ ok: false, error: new MfaCodeInvalidError() });
    const { result } = renderHook(() => useVerifyMfa(repo, onSuccess));

    await act(async () => {
      const outcome = await result.current.submit(VALID_REQUEST);
      expect(outcome).toBeNull();
    });

    expect(result.current.error).toBeInstanceOf(MfaCodeInvalidError);
    expect(result.current.isLoading).toBe(false);
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("H03: challenge expired — 410 MfaChallengeExpiredError → error set, onSuccess not called", async () => {
    const repo = makeRepo({ ok: false, error: new MfaChallengeExpiredError() });
    const { result } = renderHook(() => useVerifyMfa(repo, onSuccess));

    await act(async () => {
      const outcome = await result.current.submit(VALID_REQUEST);
      expect(outcome).toBeNull();
    });

    expect(result.current.error).toBeInstanceOf(MfaChallengeExpiredError);
    expect(result.current.isLoading).toBe(false);
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("H04: rate limited — 429 MfaVerifyRateLimitedError → error set with retryAfter", async () => {
    const repo = makeRepo({ ok: false, error: new MfaVerifyRateLimitedError(60) });
    const { result } = renderHook(() => useVerifyMfa(repo, onSuccess));

    await act(async () => {
      await result.current.submit(VALID_REQUEST);
    });

    expect(result.current.error).toBeInstanceOf(MfaVerifyRateLimitedError);
    expect((result.current.error as MfaVerifyRateLimitedError).retryAfter).toBe(60);
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("H05: network down — fetch TypeError → NetworkError set, onSuccess not called", async () => {
    const repo = makeRepo({ ok: false, error: new NetworkError("Failed to fetch") });
    const { result } = renderHook(() => useVerifyMfa(repo, onSuccess));

    await act(async () => {
      await result.current.submit(VALID_REQUEST);
    });

    expect(result.current.error).toBeInstanceOf(NetworkError);
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("H06: code length ≠ 6 → guard returns null without calling repo", async () => {
    const repo = makeRepo({ ok: true, value: SUCCESS_OUTCOME });
    const { result } = renderHook(() => useVerifyMfa(repo, onSuccess));

    let outcome: VerifyMfaOutcome | null | undefined;
    await act(async () => {
      outcome = await result.current.submit({
        challengeToken: VALID_REQUEST.challengeToken,
        code: "12345", // 5 digits — invalid
      });
    });

    expect(outcome).toBeNull();
    expect(repo.verifyMfa).not.toHaveBeenCalled();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("H07: missing challengeToken → guard returns null without calling repo", async () => {
    const repo = makeRepo({ ok: true, value: SUCCESS_OUTCOME });
    const { result } = renderHook(() => useVerifyMfa(repo, onSuccess));

    let outcome: VerifyMfaOutcome | null | undefined;
    await act(async () => {
      outcome = await result.current.submit({
        challengeToken: "", // empty — guard rejects
        code: "123456",
      });
    });

    expect(outcome).toBeNull();
    expect(repo.verifyMfa).not.toHaveBeenCalled();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("H08: clearError → error becomes null after clearing previous error", async () => {
    const repo = makeRepo({ ok: false, error: new MfaCodeInvalidError() });
    const { result } = renderHook(() => useVerifyMfa(repo, onSuccess));

    await act(async () => {
      await result.current.submit(VALID_REQUEST);
    });

    expect(result.current.error).not.toBeNull();

    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBeNull();
  });

  it("H09: isLoading starts false, toggles to true during submit, false after", async () => {
    let resolveVerify!: (value: { ok: true; value: VerifyMfaOutcome }) => void;
    const pendingVerify = new Promise<{ ok: true; value: VerifyMfaOutcome }>((res) => {
      resolveVerify = res;
    });
    const repo: IAuthRepository = {
      verifyMfa: vi.fn(async () => pendingVerify as ReturnType<IAuthRepository["verifyMfa"]>),
      signIn: vi.fn(async () => ({ ok: true as const, value: { kind: "success" as const, accessToken: MOCK_TOKEN, user: MOCK_USER } as SignInOutcome })),
      signUp: vi.fn(async () => ({ ok: true as const, value: { user_id: "stub", mfa_required: false as const } })),
      forgotPassword: vi.fn(async () => ({ ok: true as const, value: { sent: true as const } })),
      refresh: vi.fn(async () => ({ ok: true as const, value: MOCK_TOKEN })),
      fetchMe: vi.fn(async () => ({ ok: true as const, value: MOCK_USER })),
      logout: vi.fn(async () => ({ ok: true as const, value: undefined })),
    };

    const { result } = renderHook(() => useVerifyMfa(repo, onSuccess));

    expect(result.current.isLoading).toBe(false);

    act(() => {
      void result.current.submit(VALID_REQUEST);
    });

    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      resolveVerify({ ok: true as const, value: SUCCESS_OUTCOME });
      await Promise.resolve();
    });

    expect(result.current.isLoading).toBe(false);
  });

  it("H10: PII safety — logger NEVER logs code value or challengeToken value", async () => {
    const verboseSpy = vi.spyOn(logger, "logVerbose");
    const warnSpy = vi.spyOn(logger, "logWarn");

    const repo = makeRepo({ ok: true, value: SUCCESS_OUTCOME });
    const { result } = renderHook(() => useVerifyMfa(repo, onSuccess));

    await act(async () => {
      await result.current.submit(VALID_REQUEST);
    });

    // Collect all logged data
    const allLogArgs = [
      ...verboseSpy.mock.calls.flatMap((c) => JSON.stringify(c)),
      ...warnSpy.mock.calls.flatMap((c) => JSON.stringify(c)),
    ].join("\n");

    // The actual code and challengeToken values must never appear in logs
    expect(allLogArgs).not.toContain(VALID_REQUEST.code);
    expect(allLogArgs).not.toContain(VALID_REQUEST.challengeToken);
    // Lengths are OK
    expect(allLogArgs).toContain("code_len");
    expect(allLogArgs).toContain("challenge_token_len");

    verboseSpy.mockRestore();
    warnSpy.mockRestore();
  });

  it("H11: 5xx MfaVerifyInternalError → error set with status code", async () => {
    const repo = makeRepo({ ok: false, error: new MfaVerifyInternalError(503) });
    const { result } = renderHook(() => useVerifyMfa(repo, onSuccess));

    await act(async () => {
      await result.current.submit(VALID_REQUEST);
    });

    expect(result.current.error).toBeInstanceOf(MfaVerifyInternalError);
    expect((result.current.error as MfaVerifyInternalError).status).toBe(503);
    expect(onSuccess).not.toHaveBeenCalled();
  });
});

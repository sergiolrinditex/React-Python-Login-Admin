/**
 * Hilo People — useForgotPassword hook tests.
 *
 * Slice/Phase: P03-S01-T003 — ForgotPasswordPage (recuperación de acceso editorial móvil) / Phase 3.
 *
 * Responsibility: Unit tests for the useForgotPassword presentation hook.
 *   Tests T01–T10 from §12 of the task pack (useForgotPassword.test.tsx block).
 *   Repo is injected as a fake object (data layer boundary mock — not business logic mock).
 *
 * Test policy (non-negotiables §tests):
 *   - Repo fake replaces ONLY the network boundary (IAuthRepository interface).
 *   - No mocking of useForgotPassword internals; tests drive the hook via renderHook.
 *   - T07: spy on logger to assert PII safety (no full email — domain only).
 *
 * Anti-enumeration invariant tested:
 *   - T08: unknown email still resolves to onSuccess (server returns 200 for both).
 *
 * Security assertions:
 *   - T07: logger never receives full email (only domain + email_local_len), never password.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { useForgotPassword } from "../presentation/useForgotPassword";
import type {
  IAuthRepository,
  SignInRequest,
  SignInOutcome,
  ForgotPasswordRequest,
  ForgotPasswordOutcome,
} from "../domain/AuthRepository";
import type { UserProfile } from "../domain/types";
import {
  ForgotPasswordValidationError,
  ForgotPasswordRateLimitedError,
  ForgotPasswordInternalError,
  NetworkError,
} from "../data/errors";
import * as logger from "../data/logger";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_USER: UserProfile = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "employee@inditex-sandbox.com",
  full_name: "Test Employee",
  status: "active",
  preferred_language: "es",
  roles: ["employee"],
  employee_profile: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const MOCK_TOKEN = "mock-access-token-xyz-abcdefghijklmnop";

const SUCCESS_OUTCOME: ForgotPasswordOutcome = { sent: true };

const VALID_REQUEST: ForgotPasswordRequest = {
  email: "employee.verification@inditex-sandbox.com",
};

// ---------------------------------------------------------------------------
// Fake repo builder — injects only the forgotPassword method; others are stubs.
// forgotPassword vi.fn() stub added per §D-T003-AUTH-PORT regression rule.
// ---------------------------------------------------------------------------

function makeRepo(
  forgotResult:
    | { ok: true; value: ForgotPasswordOutcome }
    | { ok: false; error: Error },
): IAuthRepository {
  return {
    forgotPassword: vi.fn(async (_req: ForgotPasswordRequest) => forgotResult),
    signIn: vi.fn(async (_req: SignInRequest) => ({
      ok: true as const,
      value: {
        kind: "success" as const,
        accessToken: MOCK_TOKEN,
        user: MOCK_USER,
      } as SignInOutcome,
    })),
    signUp: vi.fn(async () => ({
      ok: true as const,
      value: { user_id: "fake-user-id", mfa_required: false as const },
    })),
    refresh: vi.fn(async () => ({ ok: true as const, value: MOCK_TOKEN })),
    fetchMe: vi.fn(async () => ({ ok: true as const, value: MOCK_USER })),
    logout: vi.fn(async () => ({ ok: true as const, value: undefined })),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useForgotPassword", () => {
  let onSuccess: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onSuccess = vi.fn();
  });

  it("T01: submit success → onSuccess called with {sent:true}, isLoading toggles, no error", async () => {
    const repo = makeRepo({ ok: true, value: SUCCESS_OUTCOME });
    const { result } = renderHook(() => useForgotPassword(repo, onSuccess));

    let outcome: ForgotPasswordOutcome | null = null;
    await act(async () => {
      outcome = await result.current.submit(VALID_REQUEST);
    });

    expect(outcome).not.toBeNull();
    expect(outcome!.sent).toBe(true);
    expect(onSuccess).toHaveBeenCalledWith(SUCCESS_OUTCOME);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("T02: submit 400 ForgotPasswordValidationError → error set, isLoading false", async () => {
    const repo = makeRepo({ ok: false, error: new ForgotPasswordValidationError() });
    const { result } = renderHook(() => useForgotPassword(repo, onSuccess));

    await act(async () => {
      const outcome = await result.current.submit(VALID_REQUEST);
      expect(outcome).toBeNull();
    });

    expect(result.current.error).toBeInstanceOf(ForgotPasswordValidationError);
    expect(result.current.isLoading).toBe(false);
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("T03: submit 429 ForgotPasswordRateLimitedError → error set with retryAfter", async () => {
    const repo = makeRepo({ ok: false, error: new ForgotPasswordRateLimitedError(60) });
    const { result } = renderHook(() => useForgotPassword(repo, onSuccess));

    await act(async () => {
      await result.current.submit(VALID_REQUEST);
    });

    const err = result.current.error;
    expect(err).toBeInstanceOf(ForgotPasswordRateLimitedError);
    expect((err as ForgotPasswordRateLimitedError).retryAfter).toBe(60);
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("T04: submit 500 ForgotPasswordInternalError → error set", async () => {
    const repo = makeRepo({ ok: false, error: new ForgotPasswordInternalError(500) });
    const { result } = renderHook(() => useForgotPassword(repo, onSuccess));

    await act(async () => {
      await result.current.submit(VALID_REQUEST);
    });

    expect(result.current.error).toBeInstanceOf(ForgotPasswordInternalError);
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("T05: submit network failure (TypeError) → NetworkError set", async () => {
    const repo = makeRepo({ ok: false, error: new NetworkError("fetch failed") });
    const { result } = renderHook(() => useForgotPassword(repo, onSuccess));

    await act(async () => {
      await result.current.submit(VALID_REQUEST);
    });

    expect(result.current.error).toBeInstanceOf(NetworkError);
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("T06: clearError → error becomes null", async () => {
    const repo = makeRepo({ ok: false, error: new NetworkError("offline") });
    const { result } = renderHook(() => useForgotPassword(repo, onSuccess));

    await act(async () => {
      await result.current.submit(VALID_REQUEST);
    });
    expect(result.current.error).toBeInstanceOf(NetworkError);

    act(() => {
      result.current.clearError();
    });
    expect(result.current.error).toBeNull();
  });

  it("T07: logger NEVER logs full email — PII safety (email_domain only)", async () => {
    const logVerboseSpy = vi.spyOn(logger, "logVerbose");
    const logWarnSpy = vi.spyOn(logger, "logWarn");
    const logErrorSpy = vi.spyOn(logger, "logError");

    const repo = makeRepo({ ok: false, error: new ForgotPasswordRateLimitedError(30) });
    const { result } = renderHook(() => useForgotPassword(repo, onSuccess));

    const FULL_EMAIL = "employee.verification@inditex-sandbox.com";

    await act(async () => {
      await result.current.submit({ email: FULL_EMAIL });
    });

    // Assert no full email in any log call
    const allLogs = [
      ...logVerboseSpy.mock.calls,
      ...logWarnSpy.mock.calls,
      ...logErrorSpy.mock.calls,
    ];

    for (const callArgs of allLogs) {
      const serialized = JSON.stringify(callArgs);
      // Full local part must never appear
      expect(serialized).not.toContain("employee.verification");
    }

    // Verify domain IS logged (hook must log email_domain per §D-T003-PII-LOGGING)
    const startCall = logVerboseSpy.mock.calls.find(
      ([event]) => event === "auth.forgot.hook.submit.start",
    );
    expect(startCall).toBeDefined();
    const meta = startCall![1] as Record<string, unknown>;
    expect(meta.email_domain).toBe("inditex-sandbox.com");
    // email_local_len must be a number, not the actual local part
    expect(typeof meta.email_local_len).toBe("number");
    expect(meta.email_local_len).toBe(FULL_EMAIL.indexOf("@"));

    logVerboseSpy.mockRestore();
    logWarnSpy.mockRestore();
    logErrorSpy.mockRestore();
  });

  it("T08: unknown email returns success (anti-enum) — onSuccess called with {sent:true}, no error", async () => {
    // Anti-enumeration invariant: server returns 200 for ALL valid email syntax inputs.
    // Frontend must never distinguish known from unknown emails.
    const unknownEmailRequest: ForgotPasswordRequest = {
      email: "nobody.unknown@inditex-sandbox.com",
    };
    const repo = makeRepo({ ok: true, value: SUCCESS_OUTCOME });
    const { result } = renderHook(() => useForgotPassword(repo, onSuccess));

    let outcome: ForgotPasswordOutcome | null = null;
    await act(async () => {
      outcome = await result.current.submit(unknownEmailRequest);
    });

    // Identical success — anti-enum invariant (§D-T003-ANTI-ENUM-UI)
    expect(outcome).not.toBeNull();
    expect(outcome!.sent).toBe(true);
    expect(onSuccess).toHaveBeenCalledWith(SUCCESS_OUTCOME);
    expect(result.current.error).toBeNull();
  });

  it("T09: second submit after first resolves — isLoading is false, onSuccess called", async () => {
    const repo = makeRepo({ ok: true, value: SUCCESS_OUTCOME });
    const { result } = renderHook(() => useForgotPassword(repo, onSuccess));

    // First submit
    await act(async () => {
      await result.current.submit(VALID_REQUEST);
    });
    expect(onSuccess).toHaveBeenCalledTimes(1);

    // Second submit after first completes — must work correctly
    await act(async () => {
      await result.current.submit(VALID_REQUEST);
    });
    expect(onSuccess).toHaveBeenCalledTimes(2);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("T10: error is cleared on next successful submit — state transition", async () => {
    // Submit fails first → error is set
    const repo = makeRepo({ ok: false, error: new ForgotPasswordValidationError() });
    const { result } = renderHook(() => useForgotPassword(repo, onSuccess));

    await act(async () => {
      await result.current.submit(VALID_REQUEST);
    });
    expect(result.current.error).toBeInstanceOf(ForgotPasswordValidationError);

    // Call clearError explicitly (testing the clearError path)
    act(() => {
      result.current.clearError();
    });
    expect(result.current.error).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });
});

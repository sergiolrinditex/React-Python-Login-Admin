/**
 * Hilo People — Auth repository (concrete HTTP adapter).
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *   Extended in P03-S01-T001 — SignInPage: added signIn() method.
 *   Extended in P03-S01-T002 — SignUpPage: added signUp() method (§D-T002-AUTH-DATA).
 *   Extended in P03-S01-T003 — ForgotPasswordPage: added forgotPassword() method.
 *   Extended in P03-S01-T005 — TwoFactorPage: added verifyMfa() method (§D-T005-AUTH-DATA).
 *   Extended in P03-S02-T007 — AccountPage: added updateLanguage() method
 *     (§D-T007-WRITE-SET-DRIFT-AUTHREPO: language endpoint is part of the auth/user contract,
 *      lives next to fetchMe and logout; moving to presentation/ would violate Clean Architecture).
 *
 * Responsibility: Concrete implementation of IAuthRepository (domain port).
 *   Calls the backend auth/user endpoints. All calls use authFetch (credentials:'include',
 *   X-Request-ID, Bearer injection, single-flight 401 interceptor).
 *
 * Clean Architecture: this is the DATA layer. Presentation/ depends on the port
 *   (IAuthRepository) NOT on this file directly.
 *
 * Endpoints consumed (TECHNICAL_GUIDE §6.2):
 *   - POST /api/v1/auth/sign-in  → email+password; returns SignInOutcome (no-MFA or MFA).
 *   - POST /api/v1/auth/sign-up  → email+password+full_name+legal_acceptance; returns SignUpOutcome.
 *   - POST /api/v1/auth/forgot-password → email only; anti-enum 200; returns {sent:true}.
 *   - POST /api/v1/auth/2fa/verify → challenge_id (JWT) + code; returns VerifyMfaOutcome.
 *   - POST /api/v1/auth/refresh  → cookie-only; returns new access_token.
 *   - GET  /api/v1/users/me      → Bearer required; returns UserProfile.
 *   - POST /api/v1/auth/logout   → Bearer required; 204 on success.
 *   - PATCH /api/v1/users/me/language → Bearer required; returns UserProfile (§D-T007-WRITE-SET-DRIFT-AUTHREPO).
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR on every public method.
 * Security: NEVER log password. NEVER log full email. NEVER log full name (PII).
 *   Log email_domain only. Log password_len (numeric) only.
 *   §D-T005-PII-LOGGING: NEVER log code, challengeToken, access_token. Log only lengths.
 *   §D-T007-PII-LOGGING: NEVER log token value in updateLanguage. Log token_len only.
 */

import type {
  IAuthRepository, Result,
  SignInRequest, SignInOutcome,
  SignUpRequest, SignUpOutcome,
  ForgotPasswordRequest, ForgotPasswordOutcome,
  VerifyMfaRequest, VerifyMfaOutcome,
} from "../domain/AuthRepository";
import type { UserProfile } from "../domain/types";
import {
  AuthSessionExpiredError,
  NetworkError,
  mapFetchError,
  InvalidCredentialsError,
  AccountLockedError,
  RateLimitedError,
  SigninValidationError,
  SigninInternalError,
  NonCorporateEmailError,
  LegalNotAcceptedError,
  EmailTakenError,
  PasswordPolicyError,
  SignupRateLimitedError,
  SignupValidationError,
  SignupInternalError,
  ForgotPasswordValidationError,
  ForgotPasswordRateLimitedError,
  ForgotPasswordInternalError,
  MfaPayloadInvalidError,
  MfaCodeInvalidError,
  MfaChallengeExpiredError,
  MfaVerifyRateLimitedError,
  MfaVerifyInternalError,
} from "./errors";
import { setAccessToken } from "./accessTokenStore";
import { logVerbose, logWarn, logError } from "./logger";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

// ---------------------------------------------------------------------------
// Helper: safely read response JSON
// ---------------------------------------------------------------------------

async function _safeJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) throw new Error("Empty response body");
  return JSON.parse(text) as T;
}

// ---------------------------------------------------------------------------
// Concrete repository
// ---------------------------------------------------------------------------

/**
 * Concrete AuthRepository implementation against the real backend.
 *
 * Creates a fresh instance with an onAuthFailure callback wired by AuthProvider.
 * The callback is called when a 401 cannot be recovered by refresh.
 */
export class AuthRepository implements IAuthRepository {
  private readonly _onAuthFailure: () => void;

  /**
   * @param onAuthFailure - Called when session expires and cannot be refreshed.
   */
  constructor(onAuthFailure: () => void) {
    this._onAuthFailure = onAuthFailure;
  }

  // ---------------------------------------------------------------------------
  // signIn — P03-S01-T001
  // ---------------------------------------------------------------------------

  /**
   * Calls POST /api/v1/auth/sign-in with email+password.
   * Maps success shapes (no-MFA + MFA challenge) to SignInOutcome.
   *
   * Security: uses plain fetch (not authFetch) because sign-in is public endpoint —
   *   no Bearer header needed; credentials:'include' ensures cookies are sent.
   *   X-Request-ID injected for end-to-end correlation.
   *
   * D-T001-USERFETCH-ON-SUCCESS: on no-MFA success, calls fetchMe() inline to
   *   load the UserProfile before returning SignInOutcome{kind:'success'}.
   *
   * Logging contract (§7 of pack):
   *   BEFORE: email_domain only (never local part), password_len, request_id.
   *   AFTER ok_no_mfa: token_len, expires_in, request_id.
   *   AFTER mfa: challenge_token_len, expires_in, request_id.
   *   WARN on 401, 423, 429.
   *   ERROR on network + unexpected status.
   *   NEVER: password, full token, full email.
   */
  async signIn(req: SignInRequest): Promise<Result<SignInOutcome>> {
    const requestId = crypto.randomUUID();
    const emailDomain = req.email.includes("@") ? req.email.split("@")[1] : "unknown";

    logVerbose("auth.signin.submit.start", {
      email_domain: emailDomain,
      password_len: req.password.length,
      request_id: requestId,
    });

    try {
      const response = await fetch(`${API_BASE}/api/v1/auth/sign-in`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": requestId,
        },
        body: JSON.stringify({ email: req.email, password: req.password }),
      });

      if (response.status === 401) {
        logWarn("auth.signin.submit.invalid_credentials", {
          status: 401,
          request_id: requestId,
        });
        return { ok: false, error: new InvalidCredentialsError() };
      }

      if (response.status === 423) {
        logWarn("auth.signin.submit.locked", {
          status: 423,
          request_id: requestId,
        });
        return { ok: false, error: new AccountLockedError() };
      }

      if (response.status === 429) {
        const retryAfterHeader = response.headers.get("Retry-After");
        const retryAfter = retryAfterHeader ? parseInt(retryAfterHeader, 10) : 0;
        logWarn("auth.signin.submit.rate_limited", {
          status: 429,
          retry_after: retryAfter,
          request_id: requestId,
        });
        return { ok: false, error: new RateLimitedError(isNaN(retryAfter) ? 0 : retryAfter) };
      }

      if (response.status === 400) {
        logWarn("auth.signin.submit.validation", {
          status: 400,
          request_id: requestId,
        });
        return { ok: false, error: new SigninValidationError() };
      }

      if (!response.ok) {
        logError("auth.signin.submit.unexpected", {
          status: response.status,
          request_id: requestId,
        });
        return { ok: false, error: new SigninInternalError(response.status) };
      }

      const body = await _safeJson<{
        data: {
          mfa_required: boolean;
          access_token?: string;
          token_type?: string;
          expires_in?: number;
          mfa_challenge_token?: string;
        };
      }>(response);

      if (body.data.mfa_required) {
        const challengeToken = body.data.mfa_challenge_token ?? "";
        const expiresIn = body.data.expires_in ?? 300;
        logVerbose("auth.signin.submit.mfa_required", {
          challenge_token_len: challengeToken.length,
          expires_in: expiresIn,
          request_id: requestId,
        });
        return {
          ok: true,
          value: { kind: "mfa", challengeToken, expiresIn },
        };
      }

      // No-MFA path: access_token present; call fetchMe before returning user
      const accessToken = body.data.access_token ?? "";
      const expiresIn = body.data.expires_in ?? 1800;

      logVerbose("auth.signin.submit.ok_no_mfa", {
        token_len: accessToken.length,
        expires_in: expiresIn,
        request_id: requestId,
      });

      // D-T001-USERFETCH-ON-SUCCESS: set token then fetchMe before signInAccepted
      setAccessToken(accessToken);
      const meResult = await this.fetchMe(accessToken);
      if (!meResult.ok) {
        logError("auth.signin.submit.fetchme_failed", {
          error: meResult.error.message,
          request_id: requestId,
        });
        return { ok: false, error: meResult.error };
      }

      return {
        ok: true,
        value: { kind: "success", accessToken, user: meResult.value },
      };
    } catch (err: unknown) {
      if (
        err instanceof InvalidCredentialsError ||
        err instanceof AccountLockedError ||
        err instanceof RateLimitedError ||
        err instanceof SigninValidationError ||
        err instanceof SigninInternalError
      ) {
        return { ok: false, error: err };
      }
      const domainErr = mapFetchError(err);
      logError("auth.signin.submit.network", { error: domainErr.message });
      return { ok: false, error: domainErr instanceof NetworkError ? domainErr : new NetworkError(domainErr.message) };
    }
  }

  // ---------------------------------------------------------------------------
  // signUp — P03-S01-T002 (§D-T002-AUTH-DATA)
  // ---------------------------------------------------------------------------

  /**
   * Calls POST /api/v1/auth/sign-up with email, password, full_name, legal_acceptance.
   * Returns SignUpOutcome on 201 {user_id, mfa_required:false}.
   * Does NOT create a session — user must call signIn() afterwards.
   *
   * Security:
   *   - Uses plain fetch (not authFetch) — public endpoint, no Bearer token needed.
   *   - credentials:'include' for cookie continuity; X-Request-ID injected.
   *   - NEVER log password, full email, or full_name (PII).
   *   - Log email_domain only; password_len numeric metadata only.
   *
   * Error mapping (TECHNICAL_GUIDE §6.2, task pack §5):
   *   400 AUTH_SIGNUP_NON_CORPORATE_EMAIL → NonCorporateEmailError
   *   400 AUTH_SIGNUP_LEGAL_NOT_ACCEPTED  → LegalNotAcceptedError
   *   409 AUTH_SIGNUP_EMAIL_TAKEN         → EmailTakenError (no field — anti-enum)
   *   422 AUTH_SIGNUP_INVALID_PAYLOAD (password) → PasswordPolicyError
   *   422 AUTH_SIGNUP_INVALID_PAYLOAD (other)    → SignupValidationError
   *   429 AUTH_SIGNUP_RATE_LIMITED        → SignupRateLimitedError(retryAfter)
   *   5xx                                 → SignupInternalError(status)
   *   TypeError                           → NetworkError
   *
   * Logging contract (D-T002-PII-LOGGING):
   *   BEFORE: email_domain, password_len, has_full_name, legal_accepted, request_id.
   *   AFTER ok: user_id (UUID, not PII), mfa_required, request_id.
   *   WARN on 400/409/429; ERROR on 422/5xx/network.
   *
   * @param req - SignUpRequest with email, password, full_name, legal_acceptance:true
   * @returns Result<SignUpOutcome>
   */
  async signUp(req: SignUpRequest): Promise<Result<SignUpOutcome>> {
    const requestId = crypto.randomUUID();
    const emailDomain = req.email.includes("@") ? req.email.split("@")[1] : "unknown";

    logVerbose("auth.signup.submit.start", {
      email_domain: emailDomain,
      password_len: req.password.length,
      has_full_name: req.full_name.trim().length > 0,
      legal_accepted: req.legal_acceptance,
      request_id: requestId,
    });

    try {
      const response = await fetch(`${API_BASE}/api/v1/auth/sign-up`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": requestId,
        },
        body: JSON.stringify({
          email: req.email,
          password: req.password,
          full_name: req.full_name,
          legal_acceptance: req.legal_acceptance,
        }),
      });

      if (response.status === 400) {
        const body = await _safeJson<{
          errors: Array<{ code: string; field?: string; message?: string }>;
        }>(response);
        const errCode = body.errors[0]?.code ?? "";
        const errField = body.errors[0]?.field;

        if (errCode === "AUTH_SIGNUP_NON_CORPORATE_EMAIL") {
          logWarn("auth.signup.submit.non_corporate_email", {
            status: 400,
            field: errField,
            request_id: requestId,
          });
          return { ok: false, error: new NonCorporateEmailError() };
        }

        if (errCode === "AUTH_SIGNUP_LEGAL_NOT_ACCEPTED") {
          logWarn("auth.signup.submit.legal_not_accepted", {
            status: 400,
            field: errField,
            request_id: requestId,
          });
          return { ok: false, error: new LegalNotAcceptedError() };
        }

        logWarn("auth.signup.submit.validation_400", {
          status: 400,
          code: errCode,
          field: errField,
          request_id: requestId,
        });
        return { ok: false, error: new SignupValidationError(errField) };
      }

      if (response.status === 409) {
        logWarn("auth.signup.submit.email_taken", {
          status: 409,
          request_id: requestId,
        });
        // D-T002-409-NO-FIELD: no field in response (anti-enumeration)
        return { ok: false, error: new EmailTakenError() };
      }

      if (response.status === 422) {
        const body = await _safeJson<{
          errors: Array<{ code: string; field?: string; message?: string }>;
        }>(response);
        const errField = body.errors[0]?.field;
        const errCode = body.errors[0]?.code ?? "";

        if (errField === "password" && errCode === "AUTH_SIGNUP_INVALID_PAYLOAD") {
          logWarn("auth.signup.submit.password_policy", {
            status: 422,
            field: errField,
            request_id: requestId,
          });
          return { ok: false, error: new PasswordPolicyError(errField) };
        }

        logWarn("auth.signup.submit.payload_invalid", {
          status: 422,
          field: errField,
          code: errCode,
          request_id: requestId,
        });
        return { ok: false, error: new SignupValidationError(errField) };
      }

      if (response.status === 429) {
        const retryAfterHeader = response.headers.get("Retry-After");
        const retryAfter = retryAfterHeader ? parseInt(retryAfterHeader, 10) : 0;
        logWarn("auth.signup.submit.rate_limited", {
          status: 429,
          retry_after: retryAfter,
          request_id: requestId,
        });
        return { ok: false, error: new SignupRateLimitedError(isNaN(retryAfter) ? 0 : retryAfter) };
      }

      if (response.status !== 201) {
        logError("auth.signup.submit.unexpected", {
          status: response.status,
          request_id: requestId,
        });
        return { ok: false, error: new SignupInternalError(response.status) };
      }

      // 201 Created
      const body = await _safeJson<{
        data: { user_id: string; mfa_required: false };
        meta: { request_id: string };
      }>(response);

      logVerbose("auth.signup.submit.ok", {
        user_id: body.data.user_id,
        mfa_required: body.data.mfa_required,
        request_id: requestId,
      });

      return {
        ok: true,
        value: { user_id: body.data.user_id, mfa_required: false },
      };
    } catch (err: unknown) {
      if (
        err instanceof NonCorporateEmailError ||
        err instanceof LegalNotAcceptedError ||
        err instanceof EmailTakenError ||
        err instanceof PasswordPolicyError ||
        err instanceof SignupRateLimitedError ||
        err instanceof SignupValidationError ||
        err instanceof SignupInternalError
      ) {
        return { ok: false, error: err };
      }
      const domainErr = mapFetchError(err);
      logError("auth.signup.submit.network", { error: domainErr.message });
      return {
        ok: false,
        error: domainErr instanceof NetworkError ? domainErr : new NetworkError(domainErr.message),
      };
    }
  }

  // ---------------------------------------------------------------------------
  // forgotPassword — P03-S01-T003
  // ---------------------------------------------------------------------------

  /**
   * Calls POST /api/v1/auth/forgot-password with email only.
   * Anti-enumeration: server returns 200 for ALL valid email syntax inputs.
   * UI MUST NOT distinguish between known and unknown emails.
   *
   * Security:
   *   - Uses plain fetch (not authFetch) — public endpoint.
   *   - credentials:'include' for cookie continuity; X-Request-ID injected.
   *   - NEVER log full email or password (PII).
   *   - Log email_domain + email_local_len only.
   *
   * Error mapping:
   *   400 → ForgotPasswordValidationError (rare — client zod should catch first).
   *   429 → ForgotPasswordRateLimitedError(retryAfter).
   *   5xx → ForgotPasswordInternalError(status).
   *   TypeError → NetworkError.
   *
   * @param req - { email }
   * @returns Result<ForgotPasswordOutcome, Error>
   */
  async forgotPassword(req: ForgotPasswordRequest): Promise<Result<ForgotPasswordOutcome>> {
    const requestId = crypto.randomUUID();
    const emailParts = req.email.split("@");
    const emailDomain = emailParts.length > 1 ? emailParts[1] : "unknown";
    const emailLocalLen = emailParts[0]?.length ?? 0;

    logVerbose("auth.forgot.submit.start", {
      email_domain: emailDomain,
      email_local_len: emailLocalLen,
      request_id: requestId,
    });

    try {
      const response = await fetch(`${API_BASE}/api/v1/auth/forgot-password`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": requestId,
        },
        body: JSON.stringify({ email: req.email }),
      });

      if (response.status === 400) {
        const body = await _safeJson<{
          errors: Array<{ code: string; field?: string }>;
        }>(response);
        const errField = body.errors[0]?.field;
        logWarn("auth.forgot.submit.validation_400", {
          status: 400,
          field: errField,
          request_id: requestId,
        });
        return { ok: false, error: new ForgotPasswordValidationError(errField) };
      }

      if (response.status === 429) {
        const retryAfterHeader = response.headers.get("Retry-After");
        const retryAfter = retryAfterHeader ? parseInt(retryAfterHeader, 10) : 0;
        logWarn("auth.forgot.submit.rate_limited", {
          status: 429,
          retry_after: retryAfter,
          request_id: requestId,
        });
        return { ok: false, error: new ForgotPasswordRateLimitedError(isNaN(retryAfter) ? 0 : retryAfter) };
      }

      if (!response.ok) {
        logError("auth.forgot.submit.unexpected", {
          status: response.status,
          request_id: requestId,
        });
        return { ok: false, error: new ForgotPasswordInternalError(response.status) };
      }

      // 200 — anti-enum success (sent:true regardless of email existence)
      logVerbose("auth.forgot.submit.ok", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: true, value: { sent: true } };
    } catch (err: unknown) {
      if (
        err instanceof ForgotPasswordValidationError ||
        err instanceof ForgotPasswordRateLimitedError ||
        err instanceof ForgotPasswordInternalError
      ) {
        return { ok: false, error: err };
      }
      const domainErr = mapFetchError(err);
      logError("auth.forgot.submit.network", { error: domainErr.message });
      return { ok: false, error: domainErr instanceof NetworkError ? domainErr : new NetworkError(domainErr.message) };
    }
  }

  // ---------------------------------------------------------------------------
  // verifyMfa — P03-S01-T005 (§D-T005-AUTH-DATA)
  // ---------------------------------------------------------------------------

  /**
   * Calls POST /api/v1/auth/2fa/verify with challenge_id (JWT) + code.
   *
   * §D-T005-CHALLENGE-FIELD-NAME: request body field is `challenge_id` but VALUE is
   *   the full JWT mfa_challenge_token. Despite the misleading name, the JWT is sent verbatim.
   *
   * §D-T005-USERFETCH-AFTER-MFA: on 200, the wire response contains a shorter MfaUserDto
   *   (id, email, preferred_language, roles). fetchMe() is called with the access_token
   *   to get the full UserProfile before invoking signInAccepted. This prevents pages
   *   from crashing on missing fields (full_name, employee_profile, status, etc.).
   *
   * §D-T005-AGGREGATE-401: 401 AUTH_MFA_CODE_INVALID aggregates 4 internal failure modes
   *   (wrong code, invalid challenge, missing secret, replay). UI shows ONE copy.
   *
   * §D-T005-PII-LOGGING: NEVER log code, challengeToken, or full email.
   *   Log code_len, challenge_token_len, request_id, expires_in, user_id only.
   *
   * Security:
   *   - ADR-002: uses API_BASE = import.meta.env.VITE_API_BASE_URL ?? "" (proxy-friendly).
   *   - credentials:'include' so backend can set refresh cookie.
   *   - X-Request-ID injected for end-to-end correlation.
   *   - setAccessToken() called BEFORE fetchMe (token needed for GET /users/me Bearer).
   *
   * Error mapping:
   *   400 AUTH_INVALID_PAYLOAD     → MfaPayloadInvalidError.
   *   401 AUTH_MFA_CODE_INVALID    → MfaCodeInvalidError (aggregate — anti-enum).
   *   410 AUTH_MFA_CHALLENGE_EXPIRED → MfaChallengeExpiredError.
   *   429 AUTH_MFA_VERIFY_RATE_LIMITED → MfaVerifyRateLimitedError(retryAfter).
   *   5xx                           → MfaVerifyInternalError(status).
   *   TypeError                     → NetworkError.
   *
   * @param req - { challengeToken: JWT string, code: '123456' }
   * @returns Result<VerifyMfaOutcome>
   */
  async verifyMfa(req: VerifyMfaRequest): Promise<Result<VerifyMfaOutcome>> {
    const requestId = crypto.randomUUID();

    // §D-T005-PII-LOGGING: log only lengths, never values
    logVerbose("auth.mfa.verify.submit.start", {
      challenge_token_len: req.challengeToken.length,
      code_len: req.code.length,
      request_id: requestId,
    });

    try {
      const response = await fetch(`${API_BASE}/api/v1/auth/2fa/verify`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": requestId,
        },
        // §D-T005-CHALLENGE-FIELD-NAME: wire field is challenge_id; value is the JWT
        body: JSON.stringify({ challenge_id: req.challengeToken, code: req.code }),
      });

      if (response.status === 400) {
        logWarn("auth.mfa.verify.submit.payload_invalid", {
          status: 400,
          request_id: requestId,
        });
        return { ok: false, error: new MfaPayloadInvalidError() };
      }

      if (response.status === 401) {
        // §D-T005-AGGREGATE-401: do NOT inspect error code — aggregate 401
        logWarn("auth.mfa.verify.submit.invalid_code", {
          status: 401,
          request_id: requestId,
        });
        return { ok: false, error: new MfaCodeInvalidError() };
      }

      if (response.status === 410) {
        logWarn("auth.mfa.verify.submit.challenge_expired", {
          status: 410,
          request_id: requestId,
        });
        return { ok: false, error: new MfaChallengeExpiredError() };
      }

      if (response.status === 429) {
        const retryAfterHeader = response.headers.get("Retry-After");
        const retryAfter = retryAfterHeader ? parseInt(retryAfterHeader, 10) : 0;
        logWarn("auth.mfa.verify.submit.rate_limited", {
          status: 429,
          retry_after: retryAfter,
          request_id: requestId,
        });
        return { ok: false, error: new MfaVerifyRateLimitedError(isNaN(retryAfter) ? 0 : retryAfter) };
      }

      if (!response.ok) {
        logError("auth.mfa.verify.submit.unexpected", {
          status: response.status,
          request_id: requestId,
        });
        return { ok: false, error: new MfaVerifyInternalError(response.status) };
      }

      // 200 success
      const body = await _safeJson<{
        data: {
          access_token: string;
          token_type: string;
          expires_in: number;
          // Wire shape is MfaUserDto (shorter than UserProfile)
          user: { id: string; email: string; preferred_language: string; roles: string[] };
        };
        meta: { request_id: string };
      }>(response);

      const accessToken = body.data.access_token;
      const expiresIn = body.data.expires_in;

      logVerbose("auth.mfa.verify.submit.ok_200", {
        token_len: accessToken.length,
        expires_in: expiresIn,
        request_id: requestId,
      });

      // §D-T005-USERFETCH-AFTER-MFA: set token then fetchMe for the full UserProfile
      setAccessToken(accessToken);
      const meResult = await this.fetchMe(accessToken);
      if (!meResult.ok) {
        logError("auth.mfa.verify.submit.fetchme_failed", {
          error: meResult.error.message,
          request_id: requestId,
        });
        return { ok: false, error: meResult.error };
      }

      logVerbose("auth.mfa.verify.submit.after", {
        user_id: meResult.value.id,
        expires_in: expiresIn,
        request_id: requestId,
      });

      return {
        ok: true,
        value: { accessToken, expiresIn, user: meResult.value },
      };
    } catch (err: unknown) {
      if (
        err instanceof MfaPayloadInvalidError ||
        err instanceof MfaCodeInvalidError ||
        err instanceof MfaChallengeExpiredError ||
        err instanceof MfaVerifyRateLimitedError ||
        err instanceof MfaVerifyInternalError
      ) {
        return { ok: false, error: err };
      }
      const domainErr = mapFetchError(err);
      logError("auth.mfa.verify.submit.network", { error: domainErr.message });
      return { ok: false, error: domainErr instanceof NetworkError ? domainErr : new NetworkError(domainErr.message) };
    }
  }

  /**
   * Calls POST /api/v1/auth/refresh (no body; refresh cookie auto-sent).
   * Returns the new access token string on 200; error on 401 or network failure.
   */
  async refresh(): Promise<Result<string>> {
    logVerbose("auth.repo.refresh.start");
    try {
      const requestId = crypto.randomUUID();
      const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "X-Request-ID": requestId },
      });

      if (response.status === 401) {
        logWarn("auth.repo.refresh.session_expired", { request_id: requestId });
        return { ok: false, error: new AuthSessionExpiredError() };
      }

      if (!response.ok) {
        logError("auth.repo.refresh.unexpected_status", {
          status: response.status,
          request_id: requestId,
        });
        return { ok: false, error: new Error(`Refresh failed: ${response.status}`) };
      }

      const body = await _safeJson<{ data: { access_token: string } }>(response);
      const token = body.data.access_token;
      logVerbose("auth.repo.refresh.ok", {
        request_id: requestId,
        token_len: token.length,
      });
      return { ok: true, value: token };
    } catch (err: unknown) {
      const domainErr = mapFetchError(err);
      logError("auth.repo.refresh.error", { error: domainErr.message });
      return { ok: false, error: domainErr };
    }
  }

  /**
   * Calls GET /api/v1/users/me with Authorization: Bearer <accessToken>.
   * Returns the UserProfile on 200; AuthSessionExpiredError on 401.
   */
  async fetchMe(accessToken: string): Promise<Result<UserProfile>> {
    logVerbose("auth.repo.fetchMe.start", { token_len: accessToken.length });
    try {
      const requestId = crypto.randomUUID();
      const response = await fetch(`${API_BASE}/api/v1/users/me`, {
        method: "GET",
        credentials: "include",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "X-Request-ID": requestId,
        },
      });

      if (response.status === 401) {
        logWarn("auth.repo.fetchMe.unauthorized", { request_id: requestId });
        return { ok: false, error: new AuthSessionExpiredError() };
      }

      if (!response.ok) {
        logError("auth.repo.fetchMe.unexpected_status", {
          status: response.status,
          request_id: requestId,
        });
        return { ok: false, error: new Error(`fetchMe failed: ${response.status}`) };
      }

      const body = await _safeJson<{ data: UserProfile }>(response);
      logVerbose("auth.repo.fetchMe.ok", {
        request_id: requestId,
        user_id: body.data.id,
      });
      return { ok: true, value: body.data };
    } catch (err: unknown) {
      const domainErr = mapFetchError(err);
      logError("auth.repo.fetchMe.error", { error: domainErr.message });
      return { ok: false, error: domainErr };
    }
  }

  // ---------------------------------------------------------------------------
  // updateLanguage — P03-S02-T007 (§D-T007-WRITE-SET-DRIFT-AUTHREPO)
  // ---------------------------------------------------------------------------

  /**
   * Calls PATCH /api/v1/users/me/language with { language } body.
   * Returns the updated UserProfile on 200; error on 400/401/422/network.
   *
   * §D-T007-WRITE-SET-DRIFT-AUTHREPO: this method is added here (data layer) rather
   *   than in presentation/useLanguagePicker.ts to preserve Clean Architecture.
   *   Language preference is an auth/user domain operation (requires Bearer token,
   *   lives next to fetchMe and logout in the same /users/me family).
   *   Precedent: same pattern as §D-T003-I18N, §D-T004-ROUTER.
   *
   * Logging contract:
   *   BEFORE: from_language (if available — uses token_len for safety), to, token_len, request_id.
   *   AFTER OK: status, user_id (UUID, not PII), request_id.
   *   AFTER ERR: status, request_id, error.message. NEVER log the token value.
   *
   * @param accessToken - Current in-memory access token (Bearer).
   * @param language - Target language: 'es' | 'en' | 'fr'.
   * @returns Result<UserProfile> — updated profile on success; error on failure.
   */
  async updateLanguage(
    accessToken: string,
    language: "es" | "en" | "fr",
  ): Promise<Result<UserProfile>> {
    const requestId = crypto.randomUUID();

    logVerbose("auth.repo.updateLanguage.start", {
      to: language,
      token_len: accessToken.length,
      request_id: requestId,
    });

    try {
      const response = await fetch(`${API_BASE}/api/v1/users/me/language`, {
        method: "PATCH",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
          "X-Request-ID": requestId,
        },
        body: JSON.stringify({ language }),
      });

      if (response.status === 401) {
        logWarn("auth.repo.updateLanguage.unauthorized", {
          status: 401,
          request_id: requestId,
        });
        return { ok: false, error: new AuthSessionExpiredError() };
      }

      if (response.status === 400 || response.status === 422) {
        logWarn("auth.repo.updateLanguage.validation", {
          status: response.status,
          to: language,
          request_id: requestId,
        });
        return {
          ok: false,
          error: new Error(
            `LANGUAGE_INVALID: language '${language}' rejected by server (${response.status})`,
          ),
        };
      }

      if (!response.ok) {
        logError("auth.repo.updateLanguage.unexpected", {
          status: response.status,
          request_id: requestId,
        });
        return {
          ok: false,
          error: new Error(`updateLanguage failed: ${response.status}`),
        };
      }

      // 200 — full UserProfile body returned (DISCREPANCY-1 resolved by P01-S02-T007)
      const body = await _safeJson<{ data: UserProfile }>(response);
      logVerbose("auth.repo.updateLanguage.ok", {
        status: response.status,
        user_id: body.data.id,
        request_id: requestId,
      });
      return { ok: true, value: body.data };
    } catch (err: unknown) {
      const domainErr = mapFetchError(err);
      logError("auth.repo.updateLanguage.error", {
        error: domainErr.message,
        request_id: requestId,
      });
      return {
        ok: false,
        error: domainErr instanceof NetworkError ? domainErr : new NetworkError(domainErr.message),
      };
    }
  }

  /**
   * Calls POST /api/v1/auth/logout with Authorization: Bearer <accessToken>.
   * Returns ok:true on 204; ok:false on 401 or network error.
   * Caller MUST clear access token REGARDLESS of result (defensive logout).
   */
  async logout(accessToken: string): Promise<Result<void>> {
    logVerbose("auth.repo.logout.start", { token_present: true });
    try {
      const requestId = crypto.randomUUID();
      const response = await fetch(`${API_BASE}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "X-Request-ID": requestId,
        },
      });

      if (response.status === 204) {
        logVerbose("auth.repo.logout.ok", { request_id: requestId });
        return { ok: true, value: undefined };
      }

      // 401 or other non-204 — still return ok:false (caller handles cleanup)
      logWarn("auth.repo.logout.non_204", {
        status: response.status,
        request_id: requestId,
      });
      return {
        ok: false,
        error: new AuthSessionExpiredError(),
      };
    } catch (err: unknown) {
      const domainErr = mapFetchError(err);
      logError("auth.repo.logout.error", { error: domainErr.message });
      return { ok: false, error: domainErr instanceof NetworkError ? domainErr : mapFetchError(err) };
    }
  }
}

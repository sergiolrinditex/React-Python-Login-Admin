# Backend Smoke Evidence — P03-S02-T004

Timestamp: 2026-05-14T14:40:00+00:00

## Sign-in flow (MFA)
- `POST /api/v1/auth/sign-in` → 200, mfa_required=true, challenge_token received
- `POST /api/v1/auth/2fa/verify` → 200, access_token received
- user_id: `51c8d4f6-f105-461f-9ea3-97f3ae2cc702`
- X-Request-ID traced through all calls

## GET /api/v1/users/me (request_id: final-smoke-003)
- HTTP status: 200
- user_id: `51c8d4f6-f105-461f-9ea3-97f3ae2cc702`
- preferred_language: `es` (initial)
- employee_profile.employee_id: `EMP-VERIFY-001`

## PATCH /api/v1/users/me/language es→fr (request_id: final-smoke-004)
- HTTP status: 200
- Response: full UserProfile body (NOT 204) — DISCREPANCY-1 confirmed resolved
- preferred_language: `fr`

## PATCH /api/v1/users/me/language fr→es reset (request_id: final-smoke-005)
- HTTP status: 200
- preferred_language: `es` (reset to initial)

## POST /api/v1/auth/logout (request_id: final-smoke-006)
- HTTP status: 204
- Refresh cookie cleared by backend (Path=/api/v1/auth)
- DB: refresh_tokens row revoked

## DB row state observed
- Before: preferred_language='es'
- After PATCH fr: preferred_language='fr'  
- After reset PATCH es: preferred_language='es'
- audit_log: rows with action='users.language.update' inserted (verified by backend behavior)

## Verification data used
- User: employee.verification@inditex-sandbox.com (Elena Verificación)
- employee_id: EMP-VERIFY-001
- Initial language: es

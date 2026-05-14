# Verify-Slice Environment Notes — P03-S01-T007

## Environment State at Verification Time

- Backend (uvicorn): http://localhost:8000 — health 200 OK, status=ok, version=0.1.0
- Frontend (Vite): http://localhost:5177 — T007 worktree frontend (started fresh)
- Note: Port 5173 was occupied by P03-S02-T002 worktree Vite process (stale/different worktree)
  - P03-S02-T002 Vite on 5173 served OLD httpClient.ts (still ?? "http://localhost:8000") 
  - T007 Vite on 5177 serves FIXED httpClient.ts (?? "")
  - This is an environment issue (parallel worktrees running); not a code defect

## Fix Verification

Source (disk): frontend/src/features/auth/data/httpClient.ts line 40
```
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
```

Vite-served (http://localhost:5177/src/features/auth/data/httpClient.ts):
```
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
```

MATCH CONFIRMED. Fix is present and active in T007 worktree.

## .env State

- frontend/.env: DOES NOT EXIST (correct — no .env overrides present)
- frontend/.env.example: VITE_API_BASE_URL= (empty pin, correct)
- No VITE_API_BASE_URL override active → fallback ?? "" fires → relative paths

## Relative URL Confirmation

All network requests observed in DevTools used http://localhost:5177/api/... (same-origin):
- POST http://localhost:5177/api/v1/auth/refresh [401, 200]
- GET http://localhost:5177/api/v1/users/me [200]
- POST http://localhost:5177/api/v1/auth/sign-in [200]
- POST http://localhost:5177/api/v1/auth/2fa/verify [400 — correct field validation]

No absolute http://localhost:8000 requests observed (those would be the BUG).
No OPTIONS/preflight requests observed.
No console errors or CORS warnings.

## Cookie Verification (from refresh response headers)

Set-Cookie: refresh_token=h_VEFuD6sK...; HttpOnly; Max-Age=2592000; Path=/api/v1/auth; SameSite=lax; Secure

Attributes:
- HttpOnly: YES (not visible to JS — confirmed via document.cookie returning only csrf_token)
- Path: /api/v1/auth (ADR-001 compliant)
- SameSite: lax (ADR-002 compliant)
- Secure: YES

## Backend Response Verification (GET /api/v1/users/me)

Response body:
{
  "data": {
    "id": "51c8d4f6-f105-461f-9ea3-97f3ae2cc702",
    "email": "employee.verification@inditex-sandbox.com",
    "full_name": "Elena Verificación",
    "status": "active",
    "preferred_language": "es",
    "roles": ["employee"],
    "employee_profile": {
      "employee_id": "EMP-VERIFY-001",
      "brand": "Zara",
      "society": "ITX-ES",
      "center": "Madrid-HQ",
      "country": "ES",
      "department": "People & Talent"
    }
  }
}

preferred_language: es — confirmed (Verification Data Contract: expected es)

## Scope Notes (J100 regression observation only, NOT journey gate)

- The 2FA redirect from SignInPage did not fire automatically (mfa_required=true but stayed on sign-in page)
- This is PRE-EXISTING and OUT OF SCOPE for T007 (T007 = data-layer fix only)
- The TwoFactorPage functionality is P03-S01-T005/T006 scope
- What was confirmed: the sign-in API call + refresh + users/me all used RELATIVE paths (same-origin)
- This is the ONLY acceptance criterion for T007

# Source-of-truth amendment — FU-20260514122959-httpclient-ts-api-base-fallback-violates-adr-002

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P03-S01-T007 | security | httpClient.ts API_BASE fallback violates ADR-002 same-origin contract | Runtime follow-up P03-S01-T002 | current | planned | high | human | P03-S01-T002 | front:auth | frontend/src/features/auth/data/httpClient.ts | J100 | — | — | — | runtime-followup#FU-20260514122959-httpclient-ts-api-base-fallback-violates-adr-002 | runtime-followup#FU-20260514122959-httpclient-ts-api-base-fallback-violates-adr-002 | Change httpClient.ts line 34 from `?? "http://localhost:8000"` to `?? ""` (same fix as authRepository.ts P03-S01-T002). All existing tests still pass. Browser flow to GET /api/v1/users/me uses relative URL /api/v1/users/me and goes through Vite proxy (dev) / Nginx (prod) per ADR-002. No CORS preflight. | /verify-slice with real corporate sandbox account — sign in → /chat must succeed in Chrome with VITE_API_BASE_URL unset, observe authFetch network panel uses relative path /api/v1/users/me, no CORS preflight, no cookie-block warnings, logs show user_id from /users/me hydration. |
```

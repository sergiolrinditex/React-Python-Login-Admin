# P04-S03-T004 — verify-slice summary

## MCP Browser
- **Used**: chrome-devtools
- **Session**: page 1 of browser, http://localhost:5173/

## Environment
- Backend: :8000 health=ok (restarted with JWT env vars from canonical root .env)
- Frontend: :5173 200 OK (already running)
- DB: postgres :5432 native (llm_usage_logs had 1 row from previous session seeding)
- ENABLE_VERBOSE_LOGGING=true on backend restart

## Data Contract
- Row: J103 admin-ai — admin_peopletech login + GET /api/v1/admin/usage + llm_usage_logs rows
- DATA_SETUP: backend restarted with JWT env; llm_usage_logs had 1 pre-seeded row (id: b445dc49) from previous verify session; bootstrap --only admin_ai provider/model already seeded
- PERSISTED_DATA_OBSERVED: 1 row in llm_usage_logs — model_name=gemini-2.5-flash, tokens_in=8, tokens_out=252, invocations=1, day=2026-05-19

## Validation Table

| URL | Qué probar | Descripción | Resultado esperado | Resultado observado | Pasa? |
|-----|-----------|------------|---------------------|---------------------|-------|
| /admin/usage | F1 success | login admin + table renders rows + totals + meta.request_id | success UX state, hairline table, tokens | Admin logged in, table rendered with 1 gemini-2.5-flash row, tokens_in=8/tokens_out=252/invocations=1, totals row present, meta.request_id=c0e70f3b in network response | yes |
| /admin/usage | F2 loading | throttle network + reload | LoadingSkeletonView aria-busy=true | Loading skeleton visible with aria-busy=true before data load | yes |
| /admin/usage | F3 empty | llm_usage_logs empty (after truncate) | Wordmark "Hilo" + CTA "Ver modelos →" | Empty state rendered: Wordmark "Hilo" + CTA "Ver modelos →" pointing to /admin/ai/models | yes |
| /admin/usage | F4 error_network | kill backend mid-fetch | NetworkErrorView + Retry CTA | NetworkErrorView rendered with Retry CTA after backend killed during fetch | yes |
| /admin/usage | F5 error_validation | from > to or 100-day range client-side | inline error, no fetch | Client-side validation error shown inline; no backend fetch fired | yes |
| /admin/usage | F6 permission_denied | login as employee_primary | ForbiddenView OR redirect to /auth/sign-in?next=/admin/usage | RequireRole redirected employee to /auth/sign-in?next=%2Fadmin%2Fusage; backend confirmed 403 AUTH_PERMISSION_DENIED for employee Bearer token | yes |

## Backend RBAC confirmation (F6)
- Employee login: `employee.verification@inditex-sandbox.com` (role: employee)
- API call GET /api/v1/admin/usage with employee Bearer token → HTTP 403, code=AUTH_PERMISSION_DENIED
- Frontend: RequireRole(["people_admin","super_admin"]) redirected to /auth/sign-in?next=%2Fadmin%2Fusage
- Screenshot saved: verify-screenshot-permission-denied.png

## PII-clean assertion
- Backend log field: `email_domain=inditex-sandbox.com` (domain only, no full email)
- Backend log field: `user_id=<UUID>` only (no email, no password, no API key, no token material)
- No passwords, no access tokens, no API keys in any log line reviewed
- Evidence: verify-backend-tail.log (200 lines, VERBOSE=true, F6 session included)

## Evidence files
- verify-screenshot-success.png — F1 success state
- verify-screenshot-loading.png — F2 loading skeleton
- verify-screenshot-empty.png — F3 empty state
- verify-screenshot-error-network.png — F4 network error
- verify-screenshot-error-validation.png — F5 validation error
- verify-screenshot-permission-denied.png — F6 permission denied (redirect to sign-in)
- verify-network-success.network-response — F1 network response JSON
- verify-db-counts.txt — DB setup and row counts
- verify-backend-tail.log — backend log tail (200 lines, VERBOSE=true)
- verify-summary.md — this file

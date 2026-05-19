# Source-of-truth amendment — FU-20260519121908-auth-store-deduplicate-concurrent-refresh-token-

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P05-S01-T007 | bug | auth store: deduplicate concurrent refresh token calls on reload to prevent race-condition logout | Runtime follow-up P05-S01-T001 | current | planned | high | human | P05-S01-T001 | journey:j100 | frontend/src/** | J100 | — | — | — | runtime-followup#FU-20260519121908-auth-store-deduplicate-concurrent-refresh-token- | runtime-followup#FU-20260519121908-auth-store-deduplicate-concurrent-refresh-token- | F5 on /chat with valid refresh cookie stays at /chat after exactly 1 successful POST /auth/refresh. Verified with Chrome DevTools network tab. | Navigate to /chat after full sign-in. Press F5. Confirm exactly 1 POST /auth/refresh call (HTTP 200, rotated cookie). Page stays at /chat. |
```

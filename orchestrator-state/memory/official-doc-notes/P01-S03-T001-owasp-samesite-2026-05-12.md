# Official Doc Note — OWASP SameSite guidance vs TECHNICAL_GUIDE §10.2

**Task**: P01-S03-T001  
**Date**: 2026-05-12  
**Severity**: low (non-blocking; SameSite=Lax is still OWASP-acceptable; the difference is preference language)  
**Sources**:
- OWASP Session Management Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- OWASP CSRF Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html

## Discrepancy

**TECHNICAL_GUIDE §10.2** specifies the refresh cookie as: `SameSite=Lax`.

**OWASP Session Management Cheat Sheet** states: *"Session cookies must explicitly set `SameSite=Strict` (preferred) or `SameSite=Lax`."* — `Strict` is labeled "preferred"; `Lax` is "acceptable alternative."

**OWASP CSRF Prevention Cheat Sheet** states: `Lax` is the OWASP-recommended *default* because *"SameSite's default Lax value provides a reasonable balance between security and usability"* — specifically it allows cookies on top-level navigations that use safe methods (GET), which is what happens when a user clicks a link to arrive at the SPA.

## Analysis

The two OWASP docs give slightly different emphasis:
- Session Management CS: prefers Strict
- CSRF CS: recommends Lax as "reasonable balance"

This is not a contradiction — they address different scenarios:
- `Strict` breaks cross-site top-level navigations (e.g., user arrives from email link → cookie NOT sent → treated as logged out). This is too strict for the refresh cookie because: (1) the refresh cookie is only sent to `/api/v1/auth` paths, not to all routes; (2) the access token is what protects API calls, not the refresh cookie directly.
- `Lax` is correct for the refresh cookie because: the cookie is scoped to `Path=/api/v1/auth` (already very restrictive), so the only cross-site scenario where Lax would be exploitable is a top-level GET navigation to `/api/v1/auth/*` — which the backend does not expose as a state-changing GET endpoint.

## Conclusion

`SameSite=Lax` in TECHNICAL_GUIDE §10.2 is OWASP-acceptable and contextually correct for this architecture. The OWASP CSRF CS explicitly recommends Lax as the default. The backend cookie is already scoped to `Path=/api/v1/auth` which provides path-level protection that Strict-over-all-paths would normally provide.

**No code change needed.** The developer should keep `SameSite=Lax` in the frontend contract and add an inline comment explaining the rationale: "Lax per OWASP CSRF CS; cookie path=/api/v1/auth already restricts scope."

## RESOLVED

RESOLVED: SameSite=Lax is OWASP-acceptable (OWASP CSRF CS recommends it as default). No change to TECHNICAL_GUIDE §10.2. Developer adds inline rationale comment.

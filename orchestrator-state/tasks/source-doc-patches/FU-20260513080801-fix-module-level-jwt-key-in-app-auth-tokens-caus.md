# Source-of-truth amendment — FU-20260513080801-fix-module-level-jwt-key-in-app-auth-tokens-caus

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P02-S02-T002 | bug | Fix module-level _JWT_KEY in app.auth.tokens causing JWT decode failures in full-suite ordering | Runtime follow-up P02-S02-T001 | current | planned | medium | human | P02-S02-T001 | security:core | backend/app/security/**, backend/tests/unit/test_security.py | — | — | — | — | runtime-followup#FU-20260513080801-fix-module-level-jwt-key-in-app-auth-tokens-caus | runtime-followup#FU-20260513080801-fix-module-level-jwt-key-in-app-auth-tokens-caus | pytest backend/tests -k security runs with 0 FAIL for TestGetMeSecurityShape. Full suite failure count does not regress. app.auth.tokens.decode_token works correctly regardless of import order in the test runner. | Run pytest backend/tests/integration/test_users_me.py::TestGetMeSecurityShape -v in both isolation and full-suite ordering — all 3 should pass. Run pytest backend/tests -v and confirm no regression vs pre-fix baseline. |
```

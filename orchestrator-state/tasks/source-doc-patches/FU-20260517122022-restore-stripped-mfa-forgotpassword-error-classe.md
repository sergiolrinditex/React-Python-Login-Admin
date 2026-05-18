# Source-of-truth amendment — FU-20260517122022-restore-stripped-mfa-forgotpassword-error-classe

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P04-S01-T005 | bug | Restore stripped MFA + ForgotPassword error classes in features/auth/data/errors.ts (regression from P04-S01-T001 commit 4a75d15) | Runtime follow-up P04-S02-T002 | current | planned | critical | human | P04-S02-T002 | front:auth | frontend/src/features/auth/data/errors.ts | J100 | — | — | — | runtime-followup#FU-20260517122022-restore-stripped-mfa-forgotpassword-error-classe | runtime-followup#FU-20260517122022-restore-stripped-mfa-forgotpassword-error-classe | frontend/src/features/auth/data/errors.ts re-exports the 8 deleted classes verbatim from 21859a4, useVerifyMfa, useForgotPassword, TwoFactorPage, ForgotPasswordPage, twoFactorHelpers compile, vite dev server boots without SyntaxError, /auth/sign-in mounts in browser, 49 baseline tsc errors and 40 pre-existing test failures resolve or shrink to a documented residual. | Hard reset + npm run -s typecheck (expect 0 errors in the previously failing auth/chat files) + npm run -s test (expect prior 40 failures to clear) + Chrome DevTools MCP navigation to /auth/sign-in and /admin/rag/collections — both must mount and render without console SyntaxError. |
```

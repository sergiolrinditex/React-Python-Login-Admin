# Source-of-truth amendment — FU-20260518084720-re-implement-accountpage-account-from-scratch-pr

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P03-S02-T007 | followup | Re-implement AccountPage /account from scratch (profile + language + logout) | Runtime follow-up P03-S02-T004 | current | planned | medium | human | P03-S02-T004 | front:account | frontend/src/pages/account/**, frontend/src/features/auth/presentation/useLogout*, frontend/src/features/auth/presentation/useLanguagePicker*, frontend/src/app/router.tsx | J100 | /account | GET /api/v1/auth/me, PATCH /api/v1/auth/me/language, POST /api/v1/auth/logout | — | runtime-followup#FU-20260518084720-re-implement-accountpage-account-from-scratch-pr | runtime-followup#FU-20260518084720-re-implement-accountpage-account-from-scratch-pr | Ruta /account renderiza AccountPage. Usuario auth ve su email + language actual. Cambio language → cookie/storage actualizado + UI re-renderiza. Click 'Logout' → cookies cleared + redirect /auth/sign-in. Tests vitest verdes. | Tras retoma DAG: login employee, navegar a /account (link en navbar), ver perfil, cambiar idioma ES→EN → texto cambia, click Logout → vuelve a /auth/sign-in. |
```

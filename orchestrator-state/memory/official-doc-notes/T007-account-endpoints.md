# T007 — AccountPage endpoint reconciliation

- Slice: P03-S02-T007 (Runtime FU of P03-S02-T004).
- Topic: endpoint family for AccountPage profile/language/logout.
- Source-of-truth files checked:
  - `docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md` lines 233, 262, 263, 258.
  - `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md` line 46 (T004 original) and line 204 (T007 FU promotion).
  - Backend code: `backend/app/users/` (router/service/repository), `backend/app/auth/routers/logout.py`.

## Discrepancy

The T007 row in the implementation checklist (line 204) cites:

- `GET /api/v1/auth/me`
- `PATCH /api/v1/auth/me/language`
- `POST /api/v1/auth/logout`

The TECHNICAL_GUIDE (§6.1 row 233 + §6.2 rows 262/263) and the backend implementation in `backend/app/users/` use:

- `GET /api/v1/users/me`
- `PATCH /api/v1/users/me/language`
- `POST /api/v1/auth/logout`

`/auth/me` and `/auth/me/language` do not exist in the backend. PROGRESS.md (T007 backend implementation, P01-S02-T007) also confirms only the `/users/me` family is wired.

The T007 acceptance and verification text are otherwise consistent with `/users/me`: profile shows email + language, PATCH updates the language, POST /logout clears the session. The acceptance can be satisfied without changing the source-of-truth — only the endpoint names need to be corrected at implementation time.

## RESOLVED

RESOLVED: using TG canonical /users/me family — CHECKLIST row endpoint cell is a typo from FU YAML promotion. Developer will call `GET /api/v1/users/me`, `PATCH /api/v1/users/me/language`, `POST /api/v1/auth/logout`. No FU is opened: this is a registry-cell typo from the FU YAML, not missing product coverage. The source-of-truth amendment (correcting the endpoint cell on line 204) is documented here and may be applied by main-orchestrator from a clean maintenance context after the slice closes, or left as-is because the canonical `/users/me` is unambiguously the contract used by TG §6.1/§6.2 and the backend.

## RESOLVED (related — journey ref typo)

The same T007 row cites `journey: J100`. TG §6.1 row 233 and instrucciones.md §3.7 Journey Coverage Matrix (J102 row) both place AccountPage on J102 (HistoryPage → ConversationPage → AccountPage). J100 is SignInPage → TwoFactorPage → ChatHomePage and does not include AccountPage. RESOLVED: this slice belongs to J102; planner records `journey_refs: ["J102"]` in the task pack. Same reasoning as the endpoint typo — no FU; orchestrator maintenance may correct the cell later.

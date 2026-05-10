# Source-of-truth amendment — FU-20260510090824-sqlalchemy-echo-leaks-argon2-hash-in-verbose-log

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P01-S02-T011 | security | SQLAlchemy echo leaks argon2 hash in verbose logs (CWE-532) | Runtime follow-up P01-S02-T001 | current | planned | medium | human | P01-S02-T001 | app:logging | backend/app/core/logging.py, backend/app/core/db.py | J100 | — | — | — | runtime-followup#FU-20260510090824-sqlalchemy-echo-leaks-argon2-hash-in-verbose-log | runtime-followup#FU-20260510090824-sqlalchemy-echo-leaks-argon2-hash-in-verbose-log | ENABLE_VERBOSE_LOGGING=true must NOT emit raw password_hash values in any logger output. SQLAlchemy echo either disabled, restricted to non-INSERT/UPDATE on auth tables, or password_hash field redacted at logging layer. Test: grep '$argon2id$' on backend stdout during a sign-up flow returns 0. | Run /verify-slice on a future auth slice with ENABLE_VERBOSE_LOGGING=true, assert grep '$argon2id$' on back.log returns 0 across happy + duplicate paths. |
```

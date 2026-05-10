# Discrepancy: email-validator not installed — EmailStr will fail at runtime

**Date**: 2026-05-10
**Task**: P01-S02-T001 (POST /api/v1/auth/sign-up)
**Severity**: BLOCKER — app fails to start (ImportError at schema construction time)
**Status**: UNRESOLVED (developer must add the dependency)

## Library + Version

- `pydantic 2.12.5` (installed in `.venv-t003`)
- `email-validator` — **NOT installed**, **NOT in `backend/requirements.txt`**

## Discrepancy

The task pack plans to use `EmailStr` from Pydantic v2 (`from pydantic import EmailStr`) in `SignUpRequest`.

**What the plan assumes**: `email-validator` is "a transitive dep" (task pack §7).

**What current docs + installed package confirm**:
- Pydantic v2 docs explicitly state: "Support for `email-validator` versions older than 2.0.0 has been dropped in Pydantic V2. Ensure you update to a compatible version using `pip install 'pydantic[email]'`."
- `email-validator` is **NOT** a transitive dependency of `pydantic` core — it is an **optional extra** (`pydantic[email]`).
- The installed `.venv-t003` confirms: `email-validator` is absent from `pip list`.
- Direct test confirms failure:

```
ImportError: email-validator is not installed, run `pip install 'pydantic[email]'`
```

This error is raised **at model class construction time** (when `class SignUpRequest(BaseModel)` is compiled), not just at validation time. That means the entire `schemas.py` module **cannot be imported**, which causes a 500 on startup and breaks all tests.

## Suggested Fix

Two equally valid approaches:

### Option A (recommended — explicit dep, production-grade)
Add `email-validator>=2.0.0` to `backend/requirements.txt` and install:
```bash
# In .venv-t003:
pip install email-validator
# Then pin the exact version:
pip freeze | grep email-validator >> backend/requirements.txt
```

### Option B (pydantic extra — same result, different install form)
```bash
pip install 'pydantic[email]'
```
This installs `email-validator` as well. But since `backend/requirements.txt` uses flat pinned deps, Option A is cleaner to maintain.

### Verification after fix
```python
from pydantic import EmailStr, BaseModel

class Test(BaseModel):
    email: EmailStr

t = Test(email='user@example.com')
assert t.email == 'user@example.com'
```
Should pass without `ImportError`.

## Source URLs
- Pydantic v2 migration docs: https://pydantic.dev/docs/validation/latest/get-started/migration (explicit note: email-validator v2+ required)
- Pydantic networks module: `/pydantic/networks.py` line 965-967 in installed 2.12.5 — `raise ImportError("email-validator is not installed, run pip install 'pydantic[email]'")`
- OWASP Password Storage: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html (argon2 — verified as non-issue, defaults exceed minimums)

## Note for developer
Do NOT add `RESOLVED:` to this note — the developer adds that line after fixing the dependency and verifying the import works.

RESOLVED: Added `email-validator==2.2.0` to `backend/pyproject.toml` (P01-S02-T001 scope). Installed in `.venv-t003` via `pip install email-validator==2.2.0`. Verified `from pydantic import EmailStr` + model construction works without ImportError. pip freeze confirmed `email-validator-2.2.0` + `dnspython-2.8.0`. requirements.txt auto-updated via pyproject.toml canonical dep list. WRITE_SET_DRIFT: pyproject.toml added to write set (not in original §10 list but required to ship the dep — same precedent as any runtime dep addition).

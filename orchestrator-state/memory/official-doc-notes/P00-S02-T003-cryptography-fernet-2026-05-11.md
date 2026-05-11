# Official Doc Note: cryptography (Fernet) explicit pin for P00-S02-T003

**Date:** 2026-05-11
**Task:** P00-S02-T003 — Verification data loader and reset
**Topic:** cryptography library availability for Fernet (MFA secret encryption)

---

## Context

Task pack §C.7 and §G capa 2 step 9 require `crypto.py` to implement:
```python
from cryptography.fernet import Fernet
encrypt_secret(plain: str, key: bytes) -> str
```

Task pack §M.7 asks researcher to confirm:
> "cryptography already in deps transitively (probably via requests/argon2-cffi). If not, add explicit pin."

---

## Internal claim (task pack §M.7)

Task pack speculates `cryptography` may be pulled transitively via requests or argon2-cffi.

---

## Official sources

- PyPI live JSON: https://pypi.org/pypi/cryptography/48.0.0/json (fetched 2026-05-11)
- PyPI live JSON: https://pypi.org/pypi/argon2-cffi/25.1.0/json (fetched 2026-05-11)
- PyPI live JSON: https://pypi.org/pypi/litellm/1.83.14/json (fetched 2026-05-11)
- PyPI live JSON: https://pypi.org/pypi/psycopg/3.3.4/json (fetched 2026-05-11)

---

## Discrepancy

**`cryptography` is NOT a transitive dependency of argon2-cffi.** argon2-cffi 25.1.0 only requires `argon2-cffi-bindings`; no cryptography in its dependency tree.

**`cryptography` is NOT a transitive dependency of psycopg 3.3.4.** psycopg's core deps are only `typing-extensions` and `tzdata`.

**`cryptography` IS a transitive dependency of litellm 1.83.14, BUT only under the `proxy` extra** (`"cryptography==46.0.7; extra == \"proxy\""`). Since the project installs `litellm==1.83.14` without the `proxy` extra (plain `litellm==1.83.14` in requirements.txt), `cryptography` is NOT guaranteed to be installed.

**Latest stable version of cryptography:** `48.0.0` (Python >=3.9, compatible with Python 3.12).

The `Fernet` class lives at `from cryptography.fernet import Fernet` — confirmed available.

---

## Recommended resolution

Developer must add an **explicit pin** for `cryptography` to avoid runtime `ImportError` in `crypto.py`:
- `backend/pyproject.toml` under `[project.dependencies]`: `"cryptography==48.0.0"`
- `backend/requirements.txt`: `cryptography==48.0.0`

This is an additional write-set extension on top of the 11 listed in §F.2. Developer must declare it in the handoff under `WRITE_SET_EXTENSIONS`.

Do NOT rely on the transitive pull from litellm's `proxy` extra — it is conditional and pinned to an older version (46.0.7).

After adding the pin, add `RESOLVED: pinned cryptography==48.0.0` to this note.

RESOLVED: pinned cryptography==48.0.0 explicitly in backend/pyproject.toml and backend/requirements.txt. Fernet import confirmed working (from cryptography.fernet import Fernet). Not relying on transitive dep from litellm proxy extra.

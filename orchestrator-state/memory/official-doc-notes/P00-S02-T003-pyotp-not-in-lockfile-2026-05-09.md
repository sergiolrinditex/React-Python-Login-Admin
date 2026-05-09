# Official Doc Note — T003: pyotp not in lockfile

**Date**: 2026-05-09
**Task**: P00-S02-T003
**Severity**: medium
**Status**: UNRESOLVED

## Context

The task pack (§ Security) states:

> "TOTP secrets: generate per-fixture using `pyotp.random_base32()` (researcher confirms whether pyotp is already a transitive dep or needs explicit declaration)."

The task pack also pre-empts with a fallback:

> "If pyotp is not in the lockfile, the developer should NOT add it as a direct dep for fixtures — use a static base32 string (`JBSWY3DPEHPK3PXP`) instead."

## Internal pattern (task pack)

```python
# Task pack suggestion A (if pyotp available):
import pyotp
totp_secret = pyotp.random_base32()

# Task pack suggestion B (fallback — static string):
totp_secret = "JBSWY3DPEHPK3PXP"  # synthetic, fixed base32
```

## Official / lockfile finding

- **pyotp 2.9.0** is the latest release (PyPI, 2026-05-09). No runtime dependencies.
- `backend/pyproject.toml` does NOT list pyotp anywhere (neither `[project.dependencies]` nor `[project.optional-dependencies]`).
- `mcp==1.27.1` direct deps confirmed (PyPI JSON API): `anyio, httpx-sse, httpx, jsonschema, pydantic-settings, pydantic, pyjwt[crypto], python-multipart, sse-starlette, starlette, typing-extensions, typing-inspection, uvicorn`. **pyotp is NOT listed.**
- pyotp has no major dependents that are in our stack (langchain, langchain-core, deepagents, litellm, argon2-cffi — none pull pyotp transitively based on PyPI metadata).
- Confirmed: pyotp is NOT a transitive dependency of any package in the current lockfile.

## Impact

The developer MUST NOT call `pyotp.random_base32()` — pyotp is not installed.

Adding pyotp as a direct dep to `backend/pyproject.toml` is NOT the right path for T003:
- It is test/fixture-only usage (a synthetic bundle artifact).
- The task pack non-negotiables rule: "Never add a package for something doable in <20 lines."
- A static base32 string (`JBSWY3DPEHPK3PXP`) is a valid synthetic TOTP secret — RFC 6238 requires a base32-encoded secret; any valid base32 string works for synthetic fixtures.

## Recommended resolution

**Option A — Static base32 string (recommended for T003)**:
```python
# data/verification/auth/mfa_primary.json
{
  "totp_secret": "JBSWY3DPEHPK3PXP",
  "algorithm": "SHA1",
  "digits": 6,
  "period": 30,
  "synthetic_totp": true
}
```
No new dep required. The Pydantic schema validates it as a string prefixed `JBSWY` or any valid base32 characters. Developer adds a docstring: "Static synthetic TOTP secret; real bundle from People Tech delivery replaces this."

**Option B — Use stdlib secrets + base64 (no pyotp needed)**:
```python
import secrets, base64
totp_secret = base64.b32encode(secrets.token_bytes(20)).decode()
```
Stdlib only. Valid for synthetic generation if the developer prefers a random value over a fixed one. Has the same fixture non-reproducibility downside (idempotency test would need to compare fixture files, not regenerate).

**Verdict**: Use Option A (static string in JSON file) for T003. The verification bundle must be deterministic and version-controlled; a random value in code would break idempotency assertions in `test_seed_idempotency.py`.

## Developer action required

1. Do NOT import pyotp.
2. Place static base32 string `JBSWY3DPEHPK3PXP` (or similar) directly in `data/verification/auth/mfa_primary.json`.
3. Add `RESOLVED: used static base32 string JBSWY3DPEHPK3PXP in JSON fixture; pyotp not added as dep.` to this note.

## RESOLVED

RESOLVED: Used static base32 string `JBSWY3DPEHPK3PXP` directly in `data/verification/auth/mfa_primary.json`. pyotp is not installed as a dep (not a transitive dep, and a static string is sufficient for a deterministic synthetic fixture). No pyotp import in any loader or schema file. Idempotency is preserved because the value is version-controlled in the JSON bundle.

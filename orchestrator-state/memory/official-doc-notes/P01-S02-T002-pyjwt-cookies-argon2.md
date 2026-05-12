# Official Doc Note: P01-S02-T002 — PyJWT pin, FastAPI/Starlette cookies, HS256 best practice, jti strategy, argon2 check_needs_rehash

**Task**: P01-S02-T002 — POST /api/v1/auth/sign-in
**Researcher**: official-docs-researcher
**Date**: 2026-05-11
**Verdict**: DECISION-AID (fills gaps in TECHNICAL_GUIDE §10.2 / §11.1; no contradiction with source-of-truth)

---

## Q1 — PyJWT current stable pin compatible with Python 3.12 stack

### Sources
- PyPI live JSON: https://pypi.org/pypi/PyJWT/json (fetched 2026-05-11)
- Context7 /jpadilla/pyjwt (Source Reputation: High, 145 snippets)

### Findings

| Item | Value |
|---|---|
| Latest stable release | **2.12.1** |
| Release date | **2026-03-13** |
| Python 3.12 classifier | Confirmed — `Programming Language :: Python :: 3.12` listed explicitly |
| Python versions supported | 3.9, 3.10, 3.11, 3.12, 3.13, 3.14 |
| Previous release | 2.12.0 (2026-03-12) |
| encode() return type in 2.x | **str** (not bytes) — changed from bytes in 1.x; 2.x consistently returns str |
| decode() signature | `jwt.decode(token, key, algorithms=["HS256"], options={...})` |
| ExpiredSignatureError | `jwt.ExpiredSignatureError` (subclass of `jwt.InvalidTokenError`) |
| InvalidTokenError | `jwt.InvalidTokenError` |
| PyJWTError | `jwt.PyJWTError` (base exception for all PyJWT errors) |
| MissingRequiredClaimError | `jwt.MissingRequiredClaimError` (raised when `options.require` list has a missing claim) |

**DECISION: Pin `PyJWT==2.12.1`** (current stable as of 2026-05-11, Python 3.12 confirmed).

Note: Task pack §F.5 mentioned `PyJWT==2.10.1` as an example. The current stable is `2.12.1`. No breaking changes in encode/decode API between 2.10.x and 2.12.x — the 2.x API is stable. Developer should use `PyJWT==2.12.1`.

---

## Q2 — FastAPI / Starlette cookie attribute API

### Sources
- Starlette official docs: https://www.starlette.io/responses/ (fetched 2026-05-11)
- FastAPI delegates cookie-setting to Starlette's `Response.set_cookie()`.

### Findings

**Exact method signature** (Starlette `Response.set_cookie`):

```python
Response.set_cookie(
    key: str,
    value: str = "",
    max_age: int | None = None,
    expires: datetime | str | int | None = None,
    path: str | None = "/",
    domain: str | None = None,
    secure: bool = False,
    httponly: bool = False,
    samesite: Literal["lax", "strict", "none"] | None = "lax",
    partitioned: bool = False,
)
```

**Key parameter names and exact casing for T002:**

| Attribute | Parameter name | Required value | Notes |
|---|---|---|---|
| HttpOnly | `httponly` | `True` | lowercase parameter name |
| Secure | `secure` | `True` | lowercase parameter name |
| SameSite | `samesite` | `"lax"` | **lowercase string `"lax"`**, NOT `"Lax"` |
| Path | `path` | `"/auth"` | accepts any path string |
| Max-Age | `max_age` | `int` (seconds) | e.g. `2592000` for 30 days |

**Important**: `samesite="none"` REQUIRES `secure=True` (browser requirement). `samesite="lax"` does not require it but T002 sets `secure=True` anyway per §10.2.

**Minimal canonical example for T002:**

```python
from fastapi.responses import JSONResponse

response = JSONResponse(content={"data": {...}, "meta": {...}, "errors": []})
response.set_cookie(
    key="refresh_token",
    value=opaque_token,
    max_age=2592000,          # AUTH_REFRESH_TTL_SECONDS
    path="/auth",             # per §10.2 + §6.4
    secure=True,
    httponly=True,
    samesite="lax",           # lowercase string
)
return response
```

**DECISION: Use `samesite="lax"` (lowercase).** Parameter names are all lowercase (`httponly`, `secure`, `samesite`, `path`, `max_age`). `Path="/auth"` is accepted via `path="/auth"`.

---

## Q3 — PyJWT HS256 best practice for 2026

### Sources
- Context7 /jpadilla/pyjwt (README.rst + usage.md + CHANGELOG.rst + llms.txt)
- RFC 7518 §3.2: https://www.rfc-editor.org/rfc/rfc7518#section-3.2 (fetched 2026-05-11)

### Findings

**Algorithm string**: `algorithm="HS256"` — confirmed correct string.

**Key length**: RFC 7518 §3.2 mandates: *"A key of the same size as the hash output (for instance, 256 bits for 'HS256') or larger MUST be used."* → minimum **32 bytes (256 bits)**. Production recommendation is ≥64 bytes (512 bits) for additional margin. Env var `JWT_PRIVATE_KEY` should be a random secret of ≥32 bytes.

**encode return type**: Confirmed `str` in PyJWT 2.x:
```python
token: str = jwt.encode(payload, key, algorithm="HS256")
# Returns str, NOT bytes
```

**Canonical encode+decode pair with required claims:**

```python
import jwt
from datetime import datetime, timezone
import uuid

# Encode (access token)
payload = {
    "sub": str(user.id),
    "email": user.email,
    "roles": user.roles,
    "preferred_language": user.preferred_language,
    "employee_profile_id": str(user.employee_profile_id),
    "jti": uuid.uuid4().hex,
    "iat": datetime.now(tz=timezone.utc),  # datetime accepted; internally converted to int
    "exp": datetime.now(tz=timezone.utc) + timedelta(seconds=access_ttl),
}
access_token: str = jwt.encode(payload, JWT_PRIVATE_KEY, algorithm="HS256")

# Decode + require specific claims
decoded = jwt.decode(
    access_token,
    JWT_PRIVATE_KEY,
    algorithms=["HS256"],
    options={"require": ["exp", "iat", "sub", "jti"]},
)
```

**`iat`/`exp` accept both `datetime` and `int`**: Confirmed by Context7 (usage.md):
- `jwt.encode({"iat": 1371720939}, "secret")` — int timestamp
- `jwt.encode({"iat": datetime.datetime.now(tz=timezone.utc)}, "secret")` — datetime
- Both are valid in PyJWT 2.x. Datetime is internally converted to UNIX timestamp int.

**`options.require` list**: The canonical require list per docs is `["exp", "iss", "sub"]`. T002 also requires `"iat"` and `"jti"` per §10.2 claims. The `options={"require": ["exp", "iat", "sub", "jti"]}` pattern is correct and raises `jwt.MissingRequiredClaimError` for any missing claim.

**DECISION: Use `algorithm="HS256"`, key ≥32 bytes, `options={"require": ["exp", "iat", "sub", "jti"]}`, datetime for `iat`/`exp` (cleaner code). Pin `PyJWT==2.12.1`.**

---

## Q4 — `jti` strategy

### Sources
- RFC 7519 §4.1.7: https://www.rfc-editor.org/rfc/rfc7519#section-4.1.7 (fetched 2026-05-11)
- OWASP JWT Cheat Sheet: attempted fetch; page returned redirect only. Using RFC 7519 as primary authority + established industry practice.

### Findings

**RFC 7519 §4.1.7** (quoted verbatim): *"The 'jti' (JWT ID) claim provides a unique identifier for the JWT. The 'jti' value is a case-sensitive string."*

The RFC requires: *"the value ensures that there is a negligible probability that the same value will be accidentally assigned to a different data object."*

No format is mandated beyond being a case-sensitive string. The RFC explicitly references UUIDs as an example of collision-resistant identifier generation. Both `uuid.uuid4().hex` (32-char hex, no hyphens) and `str(uuid.uuid4())` (36-char with hyphens) satisfy §4.1.7.

**Recommended**: `uuid.uuid4().hex` — shorter, URL-safe, RFC-compliant.

**Server-side deny-list**: For V1 with refresh token rotation, the revocation model is:
- Access tokens: short-lived (1800s); no deny-list needed — expiry handles it.
- Refresh tokens: stored hashed in `refresh_tokens.token_hash`; revoked by setting `revoked_at=now()` on use (rotation) or on logout (T004). The `jti` on access tokens serves traceability (audit correlation), not revocation.
- A full JWT deny-list (blocklist for all access tokens by jti) is required only if access tokens must be revocable mid-TTL (e.g., after password change, account lockout). That is out of scope for V1 per §F.2 and §12 invariants. T004 (logout) handles session invalidation via `refresh_tokens.revoked_at`.

**DECISION: `jti = uuid.uuid4().hex` is acceptable per RFC 7519 §4.1.7. No server-side deny-list required in V1 because refresh token rotation (T003) + `revoked_at` in `refresh_tokens` provides the revocation mechanism. Document upgrade path to access-token blocklist (e.g., Redis) in code comments for future phases.**

---

## Q5 — Argon2 `check_needs_rehash` cost

### Sources
- argon2-cffi ReadTheDocs: https://argon2-cffi.readthedocs.io/en/stable/api.html (fetched 2026-05-11)
- Context7 /hynek/argon2-cffi (Source Reputation: High)

### Findings

**Method signature**: `PasswordHasher.check_needs_rehash(hash: str | bytes) -> bool`

**What it does**: Compares the parameters encoded in the stored hash string (time_cost, memory_cost, parallelism, hash_len, salt_len, version) against the current `PasswordHasher` instance's parameters. Returns `True` if a rehash is needed.

**I/O-free**: YES — it only parses the PHC string format header of the existing hash. No cryptographic computation, no database I/O, no network calls. It is pure string parsing.

**Performance**: Microsecond-scale. The argon2 hash string encodes parameters as a prefix (`$argon2id$v=19$m=65536,t=3,p=4$...`). Parsing that prefix is O(string_length) string operations — negligible.

**Safe to call inline on every sign-in**: YES — **the official argon2-cffi docs explicitly state**: *"it's best practice to check – and if necessary rehash – passwords after each successful authentication."* This is the documented intended use pattern: verify() → check_needs_rehash() → (conditionally) hash() → db update.

**DECISION: Call `ph.check_needs_rehash(user.password_hash)` inline after every successful `ph.verify()` in the sign-in service. It is I/O-free, microsecond-scale, and the library's documented best practice. Safe to include in the same sign-in transaction.**

---

## Discrepancy analysis

| Item | Internal doc claim | Official doc finding | Verdict |
|---|---|---|---|
| PyJWT pin example | Task pack §F.5 shows `PyJWT==2.10.1` as example | Stable is `2.12.1` as of 2026-03-13 | **DECISION-AID** — use `2.12.1`; no breaking changes in encode/decode API |
| `samesite` casing | §10.2 says `SameSite=Lax` (HTTP header notation) | Starlette API parameter value is `"lax"` lowercase | **DECISION-AID** — Python param uses `"lax"` lowercase; HTTP header is `SameSite=Lax`; no contradiction |
| HS256 key size | §11.1 declares `JWT_PRIVATE_KEY` without minimum size | RFC 7518 §3.2 mandates ≥32 bytes (256 bits) | **DECISION-AID** — .env.example should include a comment requiring ≥32-byte key |
| jti | §10.2 lists `jti` in claims; no format specified | RFC 7519 §4.1.7: any unique string; uuid4.hex satisfies | **DECISION-AID** — fills gap, no contradiction |
| check_needs_rehash | T001 task pack included but cost not confirmed | argon2-cffi docs: explicitly recommended per-auth, I/O-free | **DECISION-AID** — confirms safe to use inline |

**No discrepancies found** — all official docs fill gaps or confirm internal doc decisions. Source-of-truth (TECHNICAL_GUIDE §10.2) is compatible with all official findings.

---

## Summary for developer

```
RESOLVED: yes — developer may use these pinned values:

1. PyJWT==2.12.1  (Python 3.12 compatible; encode returns str; decode + options.require confirmed)
2. samesite="lax"  (Starlette parameter value is lowercase; path="/auth", httponly=True, secure=True, max_age=int)
3. algorithm="HS256", key ≥32 bytes, datetime for iat/exp, options={"require": ["exp","iat","sub","jti"]}
4. jti = uuid.uuid4().hex  (RFC 7519 §4.1.7 compliant; no deny-list required V1)
5. ph.check_needs_rehash(hash) inline after verify — I/O-free, microseconds, documented best practice
```

Developer is unblocked to implement JWT encoding. Required pyproject.toml addition: `"PyJWT==2.12.1"`.

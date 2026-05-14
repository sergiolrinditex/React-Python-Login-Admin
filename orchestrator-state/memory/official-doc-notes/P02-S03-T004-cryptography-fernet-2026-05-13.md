Status: RESOLVED 2026-05-13 — Fernet API stable for our use case; single-key sufficient at bootstrap

# Official-Doc Note: cryptography Fernet API — P02-S03-T004
Date: 2026-05-13
Task: P02-S03-T004
Researcher: official-docs-researcher

---

## Sources consulted

1. Context7 `/websites/cryptography_io_en` — Fernet symmetric encryption docs (Source reputation: High, Benchmark: 90.35)
   - https://cryptography.io/en/latest/fernet (Fernet class API)
   - https://cryptography.io/en/latest/_sources/fernet.rst.txt
   - https://cryptography.io/en/latest/_sources/index.rst.txt
2. WebFetch: https://cryptography.io/en/48.0.0/fernet/ — version-pinned Fernet page
3. WebFetch: https://cryptography.io/en/48.0.0/changelog/ — version 48.0.0 changelog

Verification date: 2026-05-13

---

## Q1: Is `Fernet.generate_key()` still the canonical pattern in cryptography==48.0.0?

**Answer: YES — no deprecation, no change.**

Official docs (verbatim from cryptography.io/en/48.0.0/fernet/):

> `classmethod generate_key()` — Returns a fresh URL-safe base64-encoded 32-byte key (bytes).
> "Keep this some place safe! If you lose it you'll no longer be able to decrypt messages."

The 48.0.0 changelog contains **no entries touching Fernet, generate_key, encrypt, decrypt, or MultiFernet**. The most recent Fernet-adjacent change was in 44.0.0 (added `extract_timestamp` to `MultiFernet`) — purely additive. The API surface used by this repo (`generate_key`, `Fernet(key)`, `.encrypt()`, `.decrypt()`) has been stable since at least 38.0.0.

Canonical pattern confirmed:
```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()  # returns bytes, 44-char url-safe base64
print(key.decode())           # string form for .env
```

**ASSUMPTION_CONFIRMED Q1:** Internal repo usage (`python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) is the documented canonical pattern. No deprecation in 48.x.

---

## Q2: Is `Fernet(key).encrypt(b"x")` safe as a one-shot validation smoke test?

**Answer: YES — safe to call repeatedly. No nonce-reuse or weak-IV concern.**

Official docs state Fernet uses **AES-128-CBC with a random 128-bit IV generated per call** plus HMAC-SHA256 for authenticity (the "authenticated encryption" guarantee). Each `.encrypt()` call generates a fresh random IV internally, so:

- Two calls with the same plaintext produce different ciphertexts — confirmed by our internal code comment: _"Uses random IV per call — two calls with the same input produce different ciphertexts (both decrypt correctly)."_
- There is **no nonce-reuse risk** across repeated calls; the IV is fresh each time.
- The Fernet class is explicitly documented as **thread-safe**.

For a bootstrap smoke-test/validation context (encrypt a short sentinel, discard result), calling `.encrypt()` once is equivalent to `Fernet(key)` constructor-only validation. The constructor itself raises `ValueError` on a malformed key (not the right length or encoding), so constructing `Fernet(key)` **is sufficient** to validate key format. Calling `.encrypt()` additionally confirms the instance works end-to-end but adds no security risk.

Internal code in `_get_fernet()` already uses the constructor-only pattern for validation — correct per docs.

**ASSUMPTION_CONFIRMED Q2:** Calling `.encrypt()` repeatedly (or constructor-only) is safe. No nonce-reuse concern. Constructor `Fernet(key)` alone suffices for key-format validation (raises `ValueError` on bad key).

---

## Q3: Is single-key `Fernet` sufficient for dev-bootstrap key rotation, or should `MultiFernet` be used?

**Answer: Single-key `Fernet` is sufficient for the bootstrap use case described.**

The official docs on `MultiFernet`:

> "MultiFernet implements key rotation — encrypts using the first key; attempts decryption with each key sequentially. `rotate(msg)` re-encrypts tokens under the primary key while preserving original timestamps."

**Use-case analysis:**

The slice performs a **one-time bootstrap** that rotates `ENCRYPTION_KEY` in dev `.env` **only when the value is still a placeholder** (`replace-with-dev-key`). At bootstrap time there are no existing ciphertexts encrypted with the old placeholder key (the placeholder was never a valid Fernet key — `Fernet("replace-with-dev-key")` raises `ValueError`). Therefore:

- There is **nothing to re-encrypt** — no ciphertexts exist under the placeholder.
- `MultiFernet` is for **live key rotation over real ciphertexts** (primary + fallback key during a rotation window). That is explicitly deferred to P04 hardening per `D-ENC1` / TODO comment in `encryption.py`.
- The `MFA_ENCRYPTION_KEY` for TOTP secrets is a **separate env var** with a separate Fernet instance — same API, same analysis; single-key sufficient at bootstrap.

**ASSUMPTION_CONFIRMED Q3:** Single-key `Fernet` is correct for bootstrap. `MultiFernet` is the right tool only when rotating over existing live ciphertexts (P04 hardening scope, already documented as TODO in `encryption.py`).

---

## Internal code alignment check

| Internal assumption | Official doc | Status |
|---|---|---|
| `Fernet.generate_key()` returns 44-char url-safe base64 | Confirmed — "URL-safe base64-encoded 32-byte key" | MATCH |
| `Fernet(key)` raises `ValueError` on bad key | Confirmed — constructor validates | MATCH |
| `.encrypt()` uses random IV per call | Confirmed — AES-128-CBC + random IV | MATCH |
| Single-key Fernet for bootstrap (no live ciphertexts) | Confirmed — MultiFernet only needed for live rotation | MATCH |
| `decrypt()` raises `InvalidToken` on corrupt/wrong-key | Confirmed | MATCH |
| Thread-safe | Confirmed explicitly in docs | MATCH |
| `cryptography==48.0.0` pin | No Fernet changes in 48.x; changelog clean | MATCH |

**No discrepancies found.**

RESOLVED: 2026-05-13 — All internal assumptions confirmed against official cryptography 48.0.0 docs. Fernet API is stable; single-key pattern is correct for bootstrap; MultiFernet deferred to P04 as already planned.

# Official-doc note: T013 — bash `cut` does NOT strip shell quotes; ENCRYPTION_KEY strategy (a) broken

**Date**: 2026-05-10
**Task**: P00-S02-T013
**Topic**: bash shell quoting + `grep | cut` text extraction vs. shell word-splitting
**Severity**: medium — affects the ENCRYPTION_KEY placeholder strategy (line 91 of .env.example)
**Sources**:
- POSIX shell specification (shell quoting, word-splitting)
- GNU bash manual §3.1.2.2 (single quotes) and §3.5.3 (word-splitting)
- Live test: `printf "ENCRYPTION_KEY='<change-me>'\n" | grep -E '^ENCRYPTION_KEY=' | cut -d= -f2-` → `'<change-me>'` (confirmed in bash 5.x)
- python-dotenv: `dotenv_values(stream=io.StringIO("ENCRYPTION_KEY='<change-me>'\n"))['ENCRYPTION_KEY']` → `<change-me>` (quotes stripped by dotenv parser)

## Discrepancy

The task pack (P00-S02-T013.md §"Por qué la línea 91 es excepción (a)") states:

> "Single-quote `'<change-me>'` es bash-sourceable (bash decodifica las quotes y entrega el string `<change-me>` a la variable), así que `grep | cut -d= -f2-` recupera literalmente `<change-me>` y el matcher sigue funcionando."

This is INCORRECT. `grep | cut -d= -f2-` is a text extraction tool — it does NOT invoke bash word-splitting. It extracts the literal bytes after the `=` character, which for `ENCRYPTION_KEY='<change-me>'` is `'<change-me>'` (including the single-quote characters). The shell quote stripping only happens when bash itself parses the assignment during `source`.

Consequence: `scripts/setup-from-scratch.sh` lines 99-107:
```bash
current_key="$(grep -E '^ENCRYPTION_KEY=' "$env_file" | head -1 | cut -d= -f2- || true)"
# ...
if [ -z "$current_key" ] \
    || [ "$current_key" = "<change-me>" ] \
    || [ "$current_key" = "dev-encryption-key-placeholder" ]; then
  needs_new=1
fi
```

With `ENCRYPTION_KEY='<change-me>'` in the file:
- `cut` extracts: `'<change-me>'`
- `[ "'<change-me>'" = "<change-me>" ]` → FALSE
- `needs_new=0` → script skips Fernet key regeneration
- AC2 fails: backend starts with `SecretStr("<change-me>")` as the encryption key (invalid Fernet key → runtime error on first encrypt/decrypt)

## Correct fix for line 91

The script ALREADY recognizes `dev-encryption-key-placeholder` at line 105 as a second valid placeholder. This string:
- Is bash-safe (no metacharacters, no angle brackets)
- Is already in the matcher → `needs_new=1` → Fernet key IS regenerated
- Is human-readable (clearly communicates "this needs to be replaced")
- Is compatible with pydantic-settings / python-dotenv (passed through as-is, `SecretStr("dev-encryption-key-placeholder")` — pydantic does not validate Fernet key format at startup)

**Recommended fix for line 91**:
```
ENCRYPTION_KEY=dev-encryption-key-placeholder
```
This uses option (b) — same as all other lines — and works correctly with the existing matcher without touching `scripts/setup-from-scratch.sh`.

## Alternative (if developer wants to keep single-quote approach)

Use `'<change-me>'` and update the matcher in `scripts/setup-from-scratch.sh` to also match `'<change-me>'`. But the task pack explicitly prohibits touching that script. Therefore option (b) with `dev-encryption-key-placeholder` is the only in-scope solution.

## Impact on other items in task pack strategy table

All other 10 lines (rows 1, 2, 3, 5–11) use option (b) with no metacharacters. These are NOT affected by this discrepancy — they are correct.

## Verified items (no discrepancy)

| Item | Status | Detail |
|---|---|---|
| Bash `<`/`>` in unquoted `KEY=VALUE` causes redirection error | VERIFIED | `KEY=<change-me>` → bash tries `<change-me>` as file redirect. Confirmed POSIX behavior. |
| Option (b) literal bash-safe string is canonical for .env templates | VERIFIED | No angle brackets, no metacharacters — clean POSIX assignment. Industry standard. |
| pydantic-settings 2.14.1 `SecretStr` shape validation | VERIFIED | `SecretStr` wraps any string, no format/shape validation. Zero `@field_validator`/`@model_validator` on JWT keys in config.py. |
| No strict PEM validator added in pydantic 2.12.x | VERIFIED | No such change in pydantic changelog. SecretStr is a pure wrapper type throughout 2.x. |
| 12-factor app `.env` template convention | VERIFIED | No canonical placeholder format. Community uses empty (`KEY=`) or example values (`KEY=example`). No `<angle-bracket>` standard. |
| `<change-me>` vs `__CHANGE_ME__` convention shift | VERIFIED | No ecosystem-wide convention change detected. Both forms are in use; project choice is valid. |
| `grep -q '<change-me>'` as placeholder detector pattern | VERIFIED | Standard POSIX idiom; widely used in dotenv ecosystem tooling. |

RESOLVED: 2026-05-10 — Developer detected the same matcher issue independently while reading `scripts/setup-from-scratch.sh:99-107` and applied option (b) `ENCRYPTION_KEY=dev-encryption-key-placeholder` to `.env.example:93` (matches the script's existing recognized placeholder at line 105). Verified live: `grep -n 'ENCRYPTION_KEY' .env.example` shows the bash-safe value; `bash -n .env.example` exits 0; `set -a; source .env.example; set +a; echo OK` exits 0. No script changes required. Task pack §"Por qué la línea 91 es excepción (a)" is now superseded by the developer's handoff "Strategy per line" section — keep the note for traceability.

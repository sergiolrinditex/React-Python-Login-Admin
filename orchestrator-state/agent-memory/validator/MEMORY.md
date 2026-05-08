# Validator memory — Hilo People

Patterns and conventions discovered while reviewing slices. Append-only.

## Conventions established (verified live)

- **`.gitkeep` placeholders** are valid in scaffold slices when the task pack §Impact analysis explicitly enumerates them as required layout pins. They are NOT silent write-set widening if listed in the pack. Verify the task pack itemizes them before deciding scope.
- **Module/file docstring contract** (per `01-non-negotiables.md#documentation`) requires: what it does, slice/phase, dependencies. The project follows this with a top comment block including `Slice:` and `Phase:` lines. Apply this check to every new Python and shell file.
- **Logging stub for early scaffold slices**: developer uses stdlib `logging.basicConfig` gated by `ENABLE_VERBOSE_LOGGING`. structlog lands later (T003). This is the canonical bootstrap pattern; do not flag `basicConfig` as wrong in scaffold slices, but DO flag if it persists past T003.
- **`noqa: E402` after `logging.basicConfig`** is acceptable if the import order is intentional (gate the log level before any framework imports its own logger). Look for an inline comment justifying it.

## Bootstrap-generated files vs developer edits

When `git status` shows `??` for paths under `orchestrator-state/memory/*.json`, `task-dag.*`, `active-task.*`, `active-phase.*`, `registry.json`, `runtime-state.json`, these are bootstrap artifacts, NOT developer edits in the current slice. Distinguish via:

```bash
git status --porcelain | grep -E "^( M|MM)" | grep -E "(\.claude/|docs/source-of-truth/|...)"
```

`?? ` (untracked) on those paths during the first slice after bootstrap is normal. Only `M` (modified) on protected paths signals a violation.

`ledger.jsonl` is hook-managed (PostToolUse). Modified state on it is expected and not a developer write.

## Scaffold slice acceptance baseline

For the very first slice (P00-S01-T001 type), tests are intentionally absent. Task pack states T003 introduces dependency_smoke. Do NOT block on missing tests if:

1. Task pack §Verification plan says `verify_mode=auto` and lists only structural commands.
2. Task pack §Out-of-scope explicitly defers tests to a later slice.

Block ONLY if the slice ships product code that should be testable but has zero tests.

## Security checklist baselines

- `.env.example` audit: every secret-bearing var must be `<change-me>` or non-sensitive default. Flag any real-looking value (sk-..., real domains, real ports outside dev range, etc.).
- Health endpoints: no PII, no tokens, no DB connection strings in response or logs. Only status/version/uptime.
- Always check for `noqa`/`type: ignore`/`@ts-ignore` and require an inline justification.

## Useful gates / scripts

- `bash scripts/check-progress-updated.sh --auto` — exit 0 pass / 1 missing / 2 docs-only / 3 inconclusive / 4 error. Must run on every review.
- `bash scripts/check-journey-matrix.sh` — exit 0 if matrix coherent. Run when the diff touches any pantalla/endpoint/tabla declared in TECHNICAL_GUIDE §6 or instrucciones.md §3.5/§3.7.

## Red flags learned

### From P00-S01-T003 (backend dependency pack)

- **Eager module-level engine init at last line of file** is a recurring smell when developers want to "expose engine for Alembic" before Alembic exists. Pattern: `engine: AsyncEngine = _get_engine()` at file bottom. Tests then need `Settings.model_construct()` workarounds to dodge env reads. Fix: replace with `def get_engine() -> AsyncEngine: return _get_engine()` — lazy public accessor. Catch this pattern on any `core/db.py`-like file and any `core/queue.py`/`core/redis.py` future analogs. The smell signature is "module-level annotated assignment that calls a builder right before the module ends."

- **Docstring lies about pinned versions** when the developer copy-pastes from researcher pin table without re-verifying after a forced downgrade. Specifically: when a constraint forces a downgrade (e.g. litellm forces pydantic 2.12.5 instead of 2.13.4), the developer must update both pyproject.toml AND every docstring that references the version. Grep for `\d+\.\d+\.\d+` in changed docstrings vs the actual pinned version in pyproject.toml.

- **Direct dep count > non-negotiable cap when source-of-truth genuinely demands it**: do NOT block. The cap in `01-non-negotiables.md §Dependencies` is a default ceiling, not a hard veto over an explicit product contract. Flag as a follow-up to record an ADR in `TECHNICAL_GUIDE §Architectural Decision Records` (cannot be done in active task; main-orchestrator promotes the followup). This pattern will repeat for any AI/RAG/MCP-heavy product.

### Logging gate refinements

- **`structlog` setup itself can skip BEFORE log** (only AFTER inside `configure_logging()`). Acceptable for self-bootstrap functions — they have no logger to log BEFORE. Do NOT flag.
- **`_REDACTED_KEYS` audit**: must include all SecretStr field names declared in `core/config.py` (jwt_secret, provider_encryption_key, litellm_master_key, resend_api_key, etc.) PLUS the generic ones (password, token, secret, api_key). Cross-check the config.py SecretStr declarations against the redaction set every slice that adds a new SecretStr.

### Smoke test realness checks (sampling)

When a slice has 30+ smoke tests covering a dep pack, sample 4–5 across categories and verify each does ONE of:
1. Import + assert symbol exists (acceptable for huge libs like boto3, langchain).
2. Import + real round-trip (preferred for security libs: argon2 hash+verify, pyjwt encode+decode, Fernet encrypt+decrypt).
3. Import + minimal in-memory instantiation (Celery with `broker="memory://"`, FastAPI app instantiation, tiktoken encoding).

NEVER acceptable: `try: import x except ImportError: pass` — that pattern PASSES even if the import broke. Flag as critical.

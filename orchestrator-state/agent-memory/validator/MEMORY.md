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

### From P00-S01-T004 (frontend design tokens & editorial system)

- **Path A bootstrap-completion drift is real and recurring.** When a planner pack declares Path A (write_set_extension justified by §6.2/§6.3), it usually anticipates the listed bootstrap files but MISSES "tail" files that are functionally inseparable. Examples surfaced: `frontend/src/app/providers.tsx` (one-line type-only import fix needed because the new `tsconfig.json` enables `verbatimModuleSyntax: true`), `frontend/vitest.config.ts` (needs setupFiles + react plugin + alias for the new tests), `frontend/src/test/setup.ts` (new, jest-dom + cleanup), `frontend/src/vite-env.d.ts` (new, CSS side-effect imports).
  - Validator decision pattern: if the pack §6.3 spirit clearly covers them (build/test gate cannot pass otherwise) → NOT blocking, but ALWAYS recommend a `/register-followup propose` so the source-of-truth Coverage Registry write_set captures the full extension.
- **CSS tokens jsdom assertion pattern**: tests must use `getAttribute('style').toContain('var(--token)')` — NOT `toHaveStyle({ prop: 'var(--token)' })`. jsdom does NOT resolve CSS custom properties in computed styles. The first pattern is realness-preserving (asserts the actual inline style attribute the component emits); the second silently passes for the wrong reasons. Flag the second as anti-pattern.
- **TS const mirror of CSS tokens**: acceptable IF and ONLY IF it exports NAMES (the `--var-name` strings) and never VALUES. Catch the smell: any `as const` object whose values look like `'#0a0a0a'` or `'1rem'` is duplicating values and creates drift. Confirm with a self-test like `expect(value).toMatch(/^--/)`.
- **Editorial "zero rounded corners" enforcement**: verify both directions:
  1. The token: `--radius: 0` declared in `tokens.css`.
  2. The reset: `* { border-radius: var(--radius); }` applied globally in `reset.css`.
  3. Every component sets `borderRadius: 'var(--radius)'` explicitly (defense in depth).
  4. Grep negative test: `grep -rEn "border-radius:\s*[1-9]" frontend/src/` and `grep -rEn "rounded-(sm|md|lg|...)"` MUST return zero hits outside the theme root.
- **Showcase / dev-only surfaces are exempt from UX_CONTRACT marginal-states**. Routes NOT listed in UX_CONTRACT Screen inventory are dev-only. Required marginal states (loading/empty/error_*/permission_denied/success) all `n/a` with documented rationale. Validator must verify the route is genuinely absent from the screen inventory before accepting `n/a`.
- **`@testing-library/jest-dom/vitest` (not `/extend-expect`)** is the v6 + Vitest 4 import form. Older guides still show `/extend-expect`; that is legacy v5. Catch the wrong import in `test/setup.ts` files.
- **`afterEach(cleanup)` required when `globals: false`**: Testing Library auto-cleanup only fires when `globals: true`. Projects with `globals: false` MUST register explicit cleanup in setup, otherwise DOM accumulates across tests in the same file and causes flaky failures (multiple roles found, etc.).
- **`PROGRESS_MD_TOUCHED=yes` with high `CHANGED_FILES_COUNT`**: when the count looks insanely high (39k+), it's usually `node_modules/` or `.venv*/` showing as `??` (untracked) in a worktree-attached run. The gate logic correctly relies on `PROGRESS_MD_TOUCHED`, not on the file count. Don't be alarmed; check that the gate output is `GATE=pass` and move on.
- **File-size borderline check for showcase/demo pages**: a single dev-only showcase page at ~300–340 lines that is pure layout + tiny helper components is acceptable as long as no business logic leaks in. Recommend (not block) splitting helpers into a sibling file once the file crosses ~340 lines or a second showcase consumer arrives.

### From P00-S02-T001 (Docker compose stack — Rancher-ready)

- **Compose YAML file size**: `docker-compose.yml` for a 7-service Rancher-ready stack lands at ~320 lines. Around 40% are docstring/section comments. The "1 responsibility per file" rule is preserved (file declares topology only, not application logic). Do NOT block on the 300-line guideline for compose files at this scale; declarative service block + comments is one responsibility. Pattern signature: per-service comment block (~6 lines) + service body (~25–35 lines). Split would be `docker-compose.override.yml` for dev-only deltas, not by service count.

- **Rancher-ready 13-constraint audit table** is the canonical structure to embed in the validator review when the slice declares Kubernetes portability. Reuse the same row order; mark each cell `OK | issues:<...>` with a one-line evidence pointer (file:line, env var name, image tag, etc.).

- **Stale handoff cells while compose is correct** is a common docs-quality finding. Pattern: developer drafts the handoff first (with task-pack candidate tags), researcher reconciles → developer updates the compose file → forgets to back-port the corrections into all handoff cells (Risks Resolved, Acceptance Coverage, Contract Map, ADR seed). The handoff then contradicts itself. Resolution policy: NOT a `changes_requested` because product code is correct; FLAG as documentation finding for `closer` to reconcile before evidence-report fold-in. Critical when the ADR seed is one of the contradicting cells — the ADR fold-in must NOT carry forward the stale rationale.

- **Frontend nginx config wiring gap (Dockerfile vs build context)** is a recurring pattern in monorepos with a `infra/` peer to `frontend/`. The FE Dockerfile wants to bake `nginx/default.conf` but the Docker build context (`./frontend`) cannot see `../infra/nginx/`. Three legal solutions: (a) move config under `frontend/nginx/default.conf`; (b) use BuildKit `--build-context infra=../infra` (only viable for direct `docker build`, not compose); (c) bind-mount the config in compose `frontend` service. If the compose service is gated behind a profile and not actually consumed in the slice, this is non-blocking but MUST be a follow-up — the gap will surface the moment the FE image is consumed in a release/E2E slice.

- **Researcher RESOLVED line semantics for slices with >1 discrepancy**: a top-level `RESOLVED:` line in the official-doc-notes file is acceptable IF every per-check `RESOLVED:` line is ALSO present and points to the actual reconciliation source (URL + date). The PreToolUse docs-discrepancy hook reads RESOLVED lines per-note; partial resolutions can sneak through if only the top-level line is set. Always grep `RESOLVED:` count vs `## CHECK` count.

- **Image tag immutability check**: when a slice declares "no `:latest`, no floating `:main`", verify each `image:` line in compose has either a versioned tag (`v1.83.14-stable`, `pg18-bookworm`, `RELEASE.YYYY-MM-DDTHH-MM-SSZ`) OR a major-line tag that aliases a current stable patch (e.g., `redis:8-alpine` aliases `8.6.3-alpine`). Major-line tags are acceptable for an actively-maintained official image but should still be flagged for digest pinning in a hardening slice.

- **PID 1 discipline for placeholder workers**: the difference between `command: ["sh", "-c", "echo X && sleep infinity"]` and `command: ["python", "-c", "import time; print('X', flush=True); time.sleep(2**31)"]` matters. The shell-form launches sh as PID 1 and sleep as PID 2 — SIGTERM goes to sh, sleep is reaped abruptly, and `flush=True` is impossible. The python-form keeps Python as PID 1 (reproducible signal handling for Kubernetes), and structlog/`flush=True` reach stdout the first time. Validate placeholder commands against this; flag shell-form placeholders as Rancher-ready violations.

### From P00-S01-T005 (i18n bundles ES/EN/FR)

- **DAG-parallel write contamination check**: when reviewing a slice, always `git status --porcelain` and triage by *origin slice*, not by file name. In DAG mode another terminal may legitimately have edits to files outside your TASK_ID — those are NOT scope violations against the slice under review. Concrete signal to identify them: a file's docstring header lists a *different* `Phase/Slice` ID than the current one (here `backend/app/main.py` carried `+ P00-S02-T002` in its header — owned by the parallel slice, not T005). Confirm by reading the file's docstring before flagging.
- **Productive-copy verbatim audit**: when the source-of-truth has a key/value table (`instrucciones.md §6` here), validator must spot-check at least 3 keys × 3 locales = 9 cells against the table char-for-char, not just trust the count. Special characters are common drift vectors: `'` vs `’`, `?` vs `？`, NBSP vs space, accented vowels. A copy-paste from a markdown table that has typographic curly quotes will silently fail downstream `t()` calls if the test only checks key existence and not the exact value. Pattern: `expect(frAuth.forgot.title).toBe("Réinitialiser l'accès")` — the apostrophe must match the source table's apostrophe encoding exactly.
- **i18next syntax glitch in planner pack**: the planner can ship test snippets with the wrong i18next separator (`t('common.productName')` vs `t('common:productName')`). When the developer corrects this in implementation and documents the deviation in handoff, that is **good engineering** — not a scope violation. Validator should celebrate this and note it as a positive signal in the review. The dot is a key nesting separator inside a namespace; the colon separates namespace from key.
- **Drift detector realness**: confirm the test compares **flat key Sets** recursively, not top-level keys or counts. The signature is `new Set(flatKeys(es))).toEqual(new Set(flatKeys(en)))` where `flatKeys` is recursive. A test that only checks `Object.keys(es).length === Object.keys(en).length` is vacuous — passes when one locale has `{a:1, b:2}` and another has `{a:1, c:3}`. Look for the recursion explicitly.
- **D1 minimal seed key for namespace gaps**: when a namespace has no productive key in source-of-truth but the bundle must exist, a single seed key that matches surrounding patterns (here `mcp.servers.title`) is acceptable IF the test asserts that exact value. An empty `{}` bundle passes JSON.parse and any drift test vacuously — flag empty bundles as anti-pattern. The seed key satisfies "tests are REAL" by giving the drift detector something to compare.
- **PROGRESS.md "Updated by" tail line in DAG mode**: in parallel-slice mode, the most recent edit may be by a different TASK_ID than the slice under review. This is normal and expected. Look for the slice-specific section (here "i18n Bundles (P00-S01-T005)") and verify it survived the merge intact, rather than judging by the tail timestamp.
- **Untracked build artifacts predating the slice**: `frontend/*.tsbuildinfo`, `frontend/vite.config.{js,d.ts}`, `frontend/vitest.config.{js,d.ts}` typically appear during the first `tsc -b` / `vite build` run after T004. They are NOT introduced by an i18n slice; they predate it. Validator should: (a) confirm they appear in `git log` as predating via reasoning about when build artifacts were first generated, (b) flag for closer/maintenance to NOT stage them, (c) recommend (not block) adding them to `.gitignore` in a separate maintenance ticket. The repo `.gitignore` at root currently covers `node_modules/`, `dist/`, `*.log`, `.venv/` but misses these — recurring gap.
- **`react: { useSuspense: false }` is a positive signal**: when a slice configures eager (synchronous) i18n loading, it MUST also set `react.useSuspense: false`. Without it, downstream hooks force consumers into Suspense boundaries even though resources are already in memory. If you see eager loading without `useSuspense: false`, flag it as a follow-up — P03 productive screens will hit unnecessary Suspense plumbing otherwise.
- **Locale JSON files are exempt from `.md`-style docstring rule**: pure data files (JSON, YAML data, CSV) cannot carry docstrings (no comment syntax in standard JSON). The §Documentation rule applies to code files. Do not flag missing docstrings on locale bundles. The convention/inventory documentation belongs in the consuming module's docstring (here `frontend/src/i18n/index.ts` and `languages.ts`).

### From P00-S02-T002 re-review (post-debugger CWE-532 fix)

- **structlog `exc_info=True` + Rich tracebacks is a CWE-532 vector — auditable in EVERY slice.** structlog's `_redaction_processor` scrubs `event_dict` keys ONLY. When `exc_info=True` is set, `structlog.dev.ConsoleRenderer` invokes `RichTracebackFormatter` which defaults to `show_locals=True` and renders Python frame locals to stdout/stderr. The asyncpg/SQLAlchemy connect path stores `cparams = {host, user, password, port, database}` and `ConnectionParameters(...)` as frame locals — those bypass redaction entirely. Same pattern applies to any HTTP-client failure, secret-decoder failure, OAuth token-exchange failure, etc. **Mandatory validator check**: on EVERY slice, grep `exc_info=True` in changed code; for each occurrence, ask "what locals could the failing frame hold?" If the answer includes anything DSN-shaped, secret-shaped, or token-shaped → REJECT with `changes_requested` until either (a) `exc_info=True` is dropped and replaced with structured fields `error_class` + sanitized `detail`, OR (b) the slice configures `RichTracebackFormatter(show_locals=False)` globally. This trumps the docstring/redactor argument because redaction does NOT cover frame locals.
- **Self-correction is OK and required**: my initial T002 review wrote "exc_info=True ... acceptable; structlog redaction processor still applies to dict keys" which was a false equivalence. The handoff is append-only, so the re-review section explicitly supersedes the initial gate. Document the why so future reviewers don't repeat the conflation.
- **Test realness for log-leak regressions requires DELIBERATE frame-local binding.** A monkeypatched `OperationalError("simulated")` does NOT exercise the leak path because clean exception messages have clean stack frames. The regression test MUST build a fake call site whose failing frame deliberately binds secret values as locals before raising. Canonical pattern:
  ```python
  class _FakeAsyncConn:
      def __init__(self, cparams: dict[str,str], dsn: str) -> None:
          self.cparams = cparams; self.dsn = dsn
      async def __aenter__(self):
          cparams = self.cparams  # noqa: F841 — bound as local on purpose
          dsn = self.dsn          # noqa: F841 — bound as local on purpose
          raise OperationalError("connection refused", None, ...)  # generic str(exc)!
  ```
  The `# noqa: F841` is the signal: locals are intentional, secrets must be IN the frame and NOT in the exception message — otherwise the test could pass for the wrong reason (sanitizer cleaning the message).
- **Capture both stdout and stderr in capsys**: structlog's ConsoleRenderer writes to stderr by default. `combined = captured.out + captured.err` is the correct way to validate against either stream.
- **Verbose-mode forced reset for log-pipeline tests**: `configure_logging` is idempotent via a module-level `_configured` guard. Tests that need to validate a different verbose mode must reset the guard:
  ```python
  prev = core_logging._configured
  core_logging._configured = False
  try:
      core_logging.configure_logging(verbose=True)
      ... # exercise leak path
  finally:
      core_logging._configured = prev
  ```
  Not pristine (touches private), but acceptable for regression coverage. If the pattern recurs, recommend a `_reset_for_tests()` helper as a follow-up.
- **In-scope CWE fix vs out-of-scope architectural fix split**: when a security finding has both (a) a leak at the immediate call site AND (b) an architectural-level enabler one layer down, the correct split is: (a) close the leak by adjusting the call site within the existing write_set, AND (b) register a `severity: high` follow-up for the enabler. Touching the lower layer from the wrong slice's write_set is illegal scope expansion. HIGH severity ensures `claim_task.py` + closer + `/next-wave` block until promotion/waiver. T002 closed CWE-532 in `router.py` + `main.py` (in-scope); FU-20260509044829 tackles the global `RichTracebackFormatter(show_locals=False)` tuning in `app/core/logging.py` (out-of-scope, deferred but blocking).
- **Re-review trailer policy**: when a slice is reopened after `/verify-slice` issues_found + debugger fix, validator must append a NEW section to the handoff (header `## Validator re-review (post-debugger fix)`) — never edit the prior section. The trailer's OUTCOME on the re-review supersedes the initial trailer for closer's pre-check; closer reads the LAST validator section.
- **Specific characters in test secrets**: irrepetible randomized suffixes (e.g. `topsecret_pwd_xyz_8f3c1`, `hostxyz-debugger-fix`, `54399`) prevent false-positive collisions with uvicorn banners, sqlalchemy connection strings, or unrelated structlog meta lines. Validate by hand-grep of evidence files: those tokens should appear ONLY where the test put them. A test that uses generic strings like "secret" or "password" as the needle would silently pass against unrelated lines.

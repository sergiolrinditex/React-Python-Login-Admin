# Validator agent memory — Hilo People

## Patterns learned

### 2026-05-11 · P00-S01-T001 · backend/pyproject.toml build-backend invented API
- **Pattern**: developer wrote `build-backend = "setuptools.backends.legacy:build"` which does not exist. The canonical setuptools PEP 517 backend is `setuptools.build_meta`.
- **Verification check**: for every slice that touches `pyproject.toml`, validate the `[build-system].build-backend` value by extracting the module path and running `python3 -c "import <module>; print('OK')"`. If `ModuleNotFoundError` → emit `OUTCOME: changes_requested` / `NEXT_STATUS: needs_debug` (in-scope defect, debugger territory, NOT a FU per rule 05 triage).
- **Detection cost**: ~2s. The tester did NOT catch this because the tester only ran tests via `pytest`, never `python -m build` or `pip install -e backend/`. Validator owns this check; the tester pass on its own is insufficient evidence that the build system is valid.
- **Why this matters at greenfield**: pyproject.toml is a small file users skim, and invented PEP 517 backends (`setuptools.backends.*`, `flit_core.api.*`, etc.) look plausible. Any future `pip install -e .` or `python -m build` will fail and block CI / packaging.

## Project conventions discovered

- Backend uses Python 3.12 + FastAPI; greenfield project (P00 first slice on 2026-05-11).
- Versioning convention: `>=` range in `pyproject.toml` is acceptable when lockfile pins exact (rule 01 §Dependencies → "Pin exact versions. Use lockfiles."). Lockfile not yet created in T001 — fine, it is T003's responsibility.
- Logging convention: every endpoint emits BEFORE (`<name>.start request_id=<id>`) + AFTER (`<name>.ok request_id=<id> <metrics>`) + ERROR path with `logger.exception`. ENABLE_VERBOSE_LOGGING=true → DEBUG; false → WARNING.
- Request correlation: middleware-driven X-Request-ID propagation (read header or generate UUID v4, store in `request.state.request_id`, echo in response header).
- JWT: asymmetric RS256 (JWT_PRIVATE_KEY / JWT_PUBLIC_KEY), not symmetric — confirmed canonical via TECHNICAL_GUIDE §10.2. The task pack mentioned `JWT_SECRET` as legacy; the developer correctly overrode that with the technical-guide authority (rule 00 — source-of-truth wins).
- Tightly-coupled artifacts policy: `__init__.py` files for Python packages + smoke tests are accepted as part of the declared write_set even when not explicitly listed, IF they are strictly required by the deliverable (e.g. tests are non-negotiable per rule 01). No FU needed.

## Security patterns confirmed

- `.env.example` placeholders use `change-me-...` style — easy to grep for in CI to refuse real-looking secrets.
- CORS_ALLOWED_ORIGINS is comma-separated allowlist, never `*` wildcard.
- PROVIDER_ENCRYPTION_KEY documented as Fernet (base64-encoded 32 bytes) — matches rule 01 §Security for external-provider key encryption at rest.

## Gates run by validator on every slice

1. `bash scripts/check-progress-updated.sh --auto` → PROGRESS.md gate (exit codes mapped to `progress_md_gate` field).
2. `bash scripts/check-journey-matrix.sh` → only when slice touches matrix-declared routes/endpoints/tables/screens; T001 was foundational so skipped.
3. Read all `orchestrator-state/memory/official-doc-notes/<TASK_ID>-*.md` and confirm `RESOLVED:` line present on every note before approving.
4. For every backend slice touching `pyproject.toml` → import-test the `build-backend` value.
5. For every backend slice touching `main.py` → confirm logging BEFORE/AFTER + ERROR pattern + ENABLE_VERBOSE_LOGGING toggle.
6. File-size scan: target ~200, cap ~300 (non-UI stricter).

## Cycle-2 patterns (cross-cycle learnings)

### 2026-05-11 · P00-S01-T001 · debugger cycle 1 → validator cycle 2
- **Pattern**: a 1-line surgical fix to a known-bad PEP 517 backend converged in a single debugger cycle. Validator cycle 2 only needs to: (a) re-verify the F1 import test, (b) confirm scope is strictly the changed line(s), (c) confirm no app-code/test/pytest-config drift, (d) confirm RESOLVED markers are still present. ~5 commands total.
- **HTML-comment RESOLVED markers**: the developer wrote `<!-- RESOLVED: ... -->` HTML comments in the 3 official-doc notes. The `hook_docs_discrepancy_check.py` regex appears to expect a plain `RESOLVED:` line, so it still warns. **Decision**: accept as noise for cycle 2 (the human intent is unambiguous; the notes ARE resolved). **Future convention**: prefer plain-line `RESOLVED: <date> — <how>` (no HTML comment wrapper) to avoid hook false positives. Add this normalization to the developer agent if it recurs in T002+.
- **Cycle-2 trailer**: `OUTCOME: approved` + `NEXT_STATUS: ready_for_close` once F1 is verifiably gone AND scope is strictly the original write_set. The handoff section for cycle 2 should explicitly state `f1_status: RESOLVED` for the closer to audit.
- **Wheel companion**: `requires = ["setuptools>=68", "wheel"]` is the canonical pair for `setuptools.build_meta`. Earlier just `setuptools>=68` worked but `wheel` is needed for actual wheel builds. Debugger added it correctly; do not flag as scope creep — it is required for the same `[build-system]` block to be functionally complete.

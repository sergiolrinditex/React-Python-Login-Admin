# Debugger — Manual Memory

> Reflexion-style notes. Append-only. Newest entries at the top.

## 2026-05-11 — P00-S01-T003 (debug cycle 1/3) — Validator false-positive pattern + langchain meta-package pin

### Root causes
1. **Meta-package transitive drift** — `langchain==1.2.18` (post-1.x) is a meta-package. Pinning only the meta lets pip resolve the three split sub-packages (`langchain-core`, `langchain-community`, `langchain-text-splitters`) transitively at install time, breaking the "pin exact versions" non-negotiable. Whenever a dep moves to a meta-package distribution model, audit the canonical researcher note for "Additional packages" / "Split packages" tables and pin EACH sub-package explicitly, then mirror in the smoke test.
2. **Stale canonical researcher note vs PyPI live** — researcher canonical note rows may be stale by the time the developer runs. AI/ML stack moves fast; a minor-version difference between researcher note and PyPI live is the norm, not the exception.

### Fixes applied
- Added explicit pins for the 3 langchain split packages to `pyproject.toml` + `requirements.txt` + smoke test (1 pin = 1 smoke).
- Realigned the researcher canonical note to PyPI live, keeping `RESOLVED: yes` and adding an `UPDATED: <date> by debugger` block. Did NOT alter the pin the developer chose (which matched PyPI live).
- Refused to apply the validator-proposed downgrade because PyPI live evidence contradicted the canonical note. Refusing a fix backed by evidence is part of the job.

### Patterns / gotchas to remember
- **"Process defect" ≠ "runtime defect"** — validator may flag a process drift (pin vs canonical note) that, when checked against PyPI live, turns out to be the note being stale, not the code being wrong. Always re-check PyPI/Context7 for AI/ML libs before applying a "downgrade-to-match-the-note" fix.
- **Validator + tester can both report the same blocker** because they read the same canonical note — does not increase the probability that the finding is correct. Treat the source-of-truth-vs-reality chain independently.
- **Researcher notes are append-only with `UPDATED:` blocks**, not destructive edits. Preserve `RESOLVED: yes` history; append the new evidence. This keeps audit trail.
- **In DAG worktrees**: the per-terminal worktree (`/.claude/worktrees/agent-*`) may NOT contain the developer's uncommitted changes — they may live in the main repo path. Always read/write with absolute paths to the main repo root when the task pack defines paths relative to repo root. The Edit tool honored absolute paths and wrote to main correctly.
- **Smoke test symmetry**: when you add a pin, add the corresponding smoke case in the same commit. "1 pin = 1 smoke" prevents silent missing pins from passing the verify gate later.
- **LangChain ecosystem split**: `langchain` 1.x ships as meta only. The actual loaders/splitters/core live in:
  - `langchain-core` (abstractions)
  - `langchain-community` (loaders, vector stores)
  - `langchain-text-splitters` (RAG text chunking)
  Any backend RAG slice must declare all four.

### Verification commands that proved the fix
```bash
# Re-check PyPI live for any AI/ML pin disputed by the canonical note
curl -sf https://pypi.org/pypi/<package>/json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['info']['version']); print(d['info']['requires_python']); print([r for r in d['info']['requires_dist'] if '<peer-dep>' in r.lower()])"

# Reinstall + verify installed versions match declared pins
pip3 install -r backend/requirements.txt -r backend/requirements-test.txt -r backend/requirements-dev.txt
python3 -c "import importlib.metadata as m; [print(p,'->',m.version(p)) for p in ('langchain','langchain-core','langchain-community','langchain-text-splitters','pytest-asyncio')]"

# Smoke + full suite both verbose modes
cd backend && ENABLE_VERBOSE_LOGGING=true  python3 -m pytest tests/ -k dependency_smoke -v
cd backend && ENABLE_VERBOSE_LOGGING=false python3 -m pytest tests/ -k dependency_smoke -v
cd backend && python3 -m pytest tests/ -v
python3 -m ruff check backend/
```

### Debug cycle budget
- Used 1 of 3 cycles. Validator + tester should rerun cleanly. If they reopen the same two blockers without new evidence (PyPI live confirms 1.3.0 stable), escalate to human — that would indicate a process defect in the validator/canonical-note loop, not in the code.

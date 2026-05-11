# Debugger — Manual Memory

> Reflexion-style notes. Append-only. Newest entries at the top.

## 2026-05-11 — P00-S02-T001 (debug cycle 1/3) — Compose healthcheck binary assumption + hook regex format trap

### Root causes
1. **Healthcheck command must use a binary that EXISTS in the image, not what humans assume.** The `litellm` healthcheck used `curl -fsS http://localhost:4000/health/liveliness` because that is the canonical Docker pattern and what the official LiteLLM proxy docs document. But the upstream image `ghcr.io/berriai/litellm:v1.83.14-stable.patch.3` is a slim Python-only image: no curl, no wget, only `/app/.venv/bin/python` (Python 3.13). Net effect: `Health.Status=unhealthy` forever, even though the app responds 200 to the host. The blast radius is hidden: `depends_on: { litellm: { condition: service_healthy } }` on the `backend` service silently breaks the entire startup graph the first time someone runs `compose up -d backend`. The verify-slice human gate caught it; the compose `config --quiet` smoke alone could never catch it.
2. **`hook_docs_discrepancy_check.py` matches the literal string `RESOLVED:` (with colon).** Writing `RESOLVED 2026-05-11 — …` (no colon, em-dash separator) looks human-friendly but leaves the hook permanently warning at SessionStart even when the underlying discrepancies are 100% applied in code. Format-only defect, but corrosive: SessionStart warnings desensitize future readers ("oh, that warning has been there for weeks, ignore it") and erode the docs-vs-code reconciliation contract.

### Fixes applied
- F1: replaced the litellm healthcheck `test:` with a Python-stdlib probe using `urllib.request.urlopen(...,timeout=3)` + `sys.exit(0 if r.status==200 else 1)` wrapped in CMD-SHELL. Same timing knobs (interval/timeout/retries/start_period). No image change. No new path touched outside the canonical write_set. Inline comment added explaining the curl-absent reality so the next reader does not "fix" it back to curl.
- F3: two-character edit (`RESOLVED ` → `RESOLVED: `) on lines 110-111 of the doc-note. No content change. Pure regex-conformance.

### Patterns / gotchas to remember
- **Compose `config --quiet` + `config --services` + `dev-restart.sh --check` are static checks; they do NOT validate that the healthcheck binary exists in the image.** A YAML-valid healthcheck can be 100% syntactically correct and 100% runtime-broken. The only reliable verification is `docker compose up -d <svc>` + poll `Health.Status` + `docker inspect $CID --format '{{json .State.Health}}' | jq '.Log[-1]'` to confirm `ExitCode=0` from the actual healthcheck process inside the container. Add this to the verify-slice playbook for any new service.
- **For slim Python-only images (litellm, many ML inference servers, vendor sidecars), prefer `python -c "..."` probes over curl/wget.** The pattern that works in YAML CMD-SHELL with embedded double quotes for the URL:
  ```yaml
  test: ["CMD-SHELL", "python -c 'import urllib.request,sys; r=urllib.request.urlopen(\"http://localhost:PORT/PATH\",timeout=3); sys.exit(0 if r.status==200 else 1)' || exit 1"]
  ```
  YAML's `\"` inside a double-quoted scalar becomes a literal `"` in the resulting shell argument. `docker compose config` renders it correctly.
- **First few healthcheck attempts may exit non-zero during `start_period` — that is BY DESIGN.** Do not "fix" a probe that fails for the first 2-3 ticks if `start_period` is configured. In this case the first 2 logs showed `urllib` connection refused (uvicorn not bound yet); log #3 onwards all `exit 0`. The container correctly transitioned `starting → healthy` at tick=9 (~17 s).
- **Hook regexes are literal.** When marking a discrepancy resolved, copy the EXACT marker the hook expects (look at `hook_docs_discrepancy_check.py` source). `RESOLVED:` ≠ `RESOLVED ` ≠ `RESOLVED -`. A 1-character drift turns a closed loop into a permanent SessionStart warning. After writing the marker, always grep with the hook's regex pattern to confirm match before declaring done.
- **In-scope vs FU discipline under `/verify-slice` findings**: F1 had every in-scope criterion (path in canonical write_set, no new endpoint/route/table/journey, no Coverage Registry change, no `Write set`/`Conflict group` expansion, no human product decision). It belonged to debugger, NOT to a follow-up. F2 (host port 5432 collision) was correctly classified `scope_expansion/future_enhancement` and DEFERRED to human decision — no automatic FU spam.
- **`zsh status` is readonly.** When writing bash polling loops in inline `Bash` tool calls that may run under zsh's invocation, use a non-conflicting variable name (e.g. `LITE_STATUS`, not `status`). Otherwise the loop body silently fails with `read-only variable: status` and the for-loop never updates.
- **`docker compose exec -T` can produce no stdout under heredoc + pipe + tee in some shells.** Fallback: `docker exec -i $(docker compose ps -q <svc>) sh -c '...'` works reliably across shells. Use this for capturing inside-container probe output to evidence files.

### Verification commands that proved the fix
```bash
# Bring up just the affected service, poll until healthy, capture full Health.Log
export PATH="/Applications/Rancher Desktop.app/Contents/Resources/resources/darwin/bin:$PATH"
docker compose down -v && cp .env.example .env && docker compose up -d litellm
for i in $(seq 1 30); do
  LITE_STATUS=$(docker compose ps --format '{{.Status}}' litellm)
  echo "tick=$i status=$LITE_STATUS"
  echo "$LITE_STATUS" | grep -q '(healthy)' && break
  sleep 2
done

# Exact one-liner the YAML runs, executed inside the container
CID=$(docker compose ps -q litellm)
docker exec -i "$CID" sh -c 'python -c "import urllib.request,sys; r=urllib.request.urlopen('"'"'http://localhost:4000/health/liveliness'"'"',timeout=3); sys.exit(0 if r.status==200 else 1)"'
echo "INSIDE_EXIT=$?"

# Counter-evidence (curl/wget absent, python present)
docker exec -i "$CID" sh -c 'printf "curl=%s\nwget=%s\npython=%s\n" "$(command -v curl)" "$(command -v wget)" "$(command -v python)"'

# Confirm Health.Log healthy with failing_streak=0
docker inspect "$CID" --format='{{json .State.Health}}' | python3 -c 'import json,sys; h=json.load(sys.stdin); print("status=",h.get("Status"),"failing_streak=",h.get("FailingStreak"),"total_logs=",len(h.get("Log",[]))); [print("LOG#",i,"exit",l.get("ExitCode")) for i,l in enumerate(h.get("Log",[]))]'

# Teardown discipline
docker compose down -v && rm -f .env
```

### Debug cycle budget
- Used 1 of 3 cycles. Validator + tester should rerun cleanly on the updated handoff; if /verify-slice still flags F1 with new evidence (not the same symptom), escalate — there is at most 1 more debugger pass available before max_debug_cycles_reached.

---

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

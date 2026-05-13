#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import datetime as _dt
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import traceback
from pathlib import Path
from typing import Any, Iterable, Iterator

try:
    import fcntl  # POSIX only; hooks run on the developer machine
    _HAS_FCNTL = True
except ImportError:  # pragma: no cover — Windows fallback
    _HAS_FCNTL = False

EXCLUDED_SCAN_DIRS = {
    ".git",
    ".claude",
    "orchestrator-state",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    ".idea",
    ".vscode",
}

# Strict phase-heading regex. Matches "Phase N", "Fase N", "Phase N — title",
# "Fase 1.2 — algo". Requires a phase NUMBER (rejects "PHASE GATE",
# "PRE-GATE: Phase 0" — those would otherwise be picked up incorrectly by the
# bootstrap when scanning the checklist for the list of canonical phases).
PHASE_RE = re.compile(
    r"(?i)^\s*(?:fase|phase)\s+([0-9]+(?:\.[0-9]+)*)\s*[-—:]*\s*(.*)$"
)
CHECKBOX_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s*\[(?: |x|X)\]\s+(.*\S)\s*$")
BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+(.*\S)\s*$")
CANONICAL_SOURCE_DOCS_DIR = Path("docs/source-of-truth")


def _resolve_main_repo(start: Path) -> Path:
    """Walk up from ``start`` looking for a ``.git`` marker.

    When the marker is a directory, return the directory containing it.
    When the marker is a *file* (the canonical worktree marker — git stores a
    plain text file with ``gitdir: <abs path>/worktrees/<name>``), resolve to
    the main repo by stripping the ``/worktrees/<name>`` suffix from that
    path. This guarantees that registry, runtime-state and ledger writes
    always land under the main repo's ``orchestrator-state/`` even when a hook fires from
    inside a worktree (developer/debugger/deployer agents). Falls back to
    ``start`` if no marker is found in the walk.
    """
    current = start.resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        git = candidate / ".git"
        if git.is_dir():
            return candidate
        if git.is_file():
            try:
                body = git.read_text(encoding="utf-8").strip()
                if body.startswith("gitdir:"):
                    gitdir = Path(body.split(":", 1)[1].strip())
                    if not gitdir.is_absolute():
                        gitdir = (candidate / gitdir).resolve()
                    parts = gitdir.parts
                    if "worktrees" in parts:
                        idx = parts.index("worktrees")
                        main_git_dir = Path(*parts[:idx])
                        if main_git_dir.name == ".git":
                            return main_git_dir.parent
                # Unexpected gitfile format: treat the worktree itself as root.
                return candidate
            except Exception:
                return candidate
    return start


def project_root() -> Path:
    """Resolve the canonical project root, worktree-safe.

    Order of precedence:
      1. ``CLAUDE_ORCHESTRATOR_ROOT`` — explicit override for this engine.
         Use this only when you want all hooks to write state to a fixed
         parent repository even if Claude Code is running inside a worktree.
      2. ``CLAUDE_PROJECT_DIR`` — official Claude Code project root env var.
         We still pass it through ``_resolve_main_repo`` instead of returning
         it raw: a pr-flow worker terminal may set it to the
         per-TASK_ID worktree root, and the orchestrator state must remain under the
         main repo's ``orchestrator-state/``.
      3. Walk up from this file looking for a ``.git`` marker. A directory
         marker -> repo root. A file marker -> main repo (worktree-aware).
      4. Fallback: ``parents[2]`` of this file (zip-layout fallback for a zip not
         yet initialized as a git repo).
    """
    explicit = os.environ.get("CLAUDE_ORCHESTRATOR_ROOT")
    if explicit:
        return _resolve_main_repo(Path(explicit).resolve())
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return _resolve_main_repo(Path(env).resolve())
    archived_default = Path(__file__).resolve().parents[2]
    return _resolve_main_repo(archived_default)




def _resolve_worktree_repo(start: Path) -> Path:
    """Return the actual checkout/worktree root, not the canonical main repo.

    `project_root()` intentionally resolves a git worktree back to the main repo
    so hooks write registry/runtime/handoffs in one place. Product commands are
    different: tests, linters and visual checks must run against the checkout
    where the TASK_ID is being implemented. When `.git` is a worktree file, this
    helper returns the directory containing that file.
    """
    current = start.resolve()
    for candidate in [current, *current.parents]:
        git = candidate / ".git"
        if git.is_dir() or git.is_file():
            return candidate
    return start.resolve()


def workspace_root(start: Path | None = None) -> Path:
    """Resolve the checkout that product code commands should operate on.

    In a task terminal this is the per-TASK_ID git worktree. In the main checkout
    it is the main repo. Orchestrator state still uses `project_root()`.
    Tests and explicit callers may set `CLAUDE_PROJECT_DIR`; unlike
    `project_root()`, this function keeps that checkout rather than resolving a
    worktree back to the canonical main repo.
    """
    explicit = (
        os.environ.get("CLAUDE_WORKTREE_ROOT")
        or os.environ.get("CLAUDE_WORKSPACE_ROOT")
        or os.environ.get("CLAUDE_PROJECT_DIR")
    )
    if explicit:
        return _resolve_worktree_repo(Path(explicit).expanduser())
    if start is not None:
        return _resolve_worktree_repo(start)
    raw_pwd = os.environ.get("PWD")
    base = Path(raw_pwd).expanduser() if raw_pwd else Path.cwd()
    if not base.is_absolute():
        base = Path.cwd() / base
    return _resolve_worktree_repo(base)


def claude_dir() -> Path:
    return project_root() / ".claude"


STATE_DIR_NAME = os.environ.get("CLAUDE_ORCHESTRATOR_STATE_DIR", "orchestrator-state")
DEFAULT_SPAWN_BUDGET = 20
# Tasks in these statuses own their declared conflict groups/write-set.
# Plain `blocked` is dependency-blocked by default and must NOT block unrelated waves;
# active_conflict_blockers() treats `blocked` as a blocker only when its deps are already satisfied.
SCHEDULER_ACTIVE_STATUSES = {"claimed", "in_progress", "validator_tester_pending", "needs_debug", "ready_for_close"}
NEUTRAL_CONFLICT_VALUES = {"", "-", "—", "none", "n/a", "na", "null", "sin conflicto", "sin conflictos", "read-only", "readonly", "no-write", "no-write-set"}



def state_dir() -> Path:
    """Mutable orchestrator state root.

    Keep this OUTSIDE `.claude/` because Claude Code protects writes to
    `.claude` even in bypassPermissions mode. `.claude/` remains static
    configuration; generated runtime, memory, handoffs, ledger and evidence
    live here. The env var is mainly for tests/CI; normal projects use
    `orchestrator-state/`.
    """
    raw = os.environ.get("CLAUDE_ORCHESTRATOR_STATE_DIR")
    if raw:
        path = Path(raw).expanduser()
        if path.is_absolute():
            return path
        return project_root() / path
    return project_root() / STATE_DIR_NAME


def memory_dir() -> Path:
    return state_dir() / "memory"


def tasks_dir() -> Path:
    return state_dir() / "tasks"


def task_packs_dir() -> Path:
    """Per-task context packs used by DAG worker terminals.

    The per-task pack is the production DAG authority. DAG-only execution has no
    global task/implicit selector.
    """
    return tasks_dir() / "task-packs"


def task_pack_path(task_id: str | None) -> Path:
    safe = str(task_id or "unknown").strip() or "unknown"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", safe)
    return task_packs_dir() / f"{safe}.md"


def agent_memory_dir() -> Path:
    return state_dir() / "agent-memory"


def canonical_source_docs_dir(root: Path | None = None) -> Path:
    root = root or project_root()
    return root / CANONICAL_SOURCE_DOCS_DIR


def scan_source_doc_candidates(root: Path) -> dict[str, list[Path]]:
    files = discover_markdown_files(root)
    instructions = [p for p in files if p.name == "instrucciones.md"]
    checklist = [p for p in files if p.name.endswith("_IMPLEMENTATION_CHECKLIST.md")]
    guide = [p for p in files if p.name.endswith("_TECHNICAL_GUIDE.md")]
    ux = [p for p in files if p.name == "UX_CONTRACT.md"]
    stack_profile = sorted((root).glob("STACK_PROFILE.yaml")) if root.exists() else []
    return {
        "instructions": instructions,
        "checklist": checklist,
        "guide": guide,
        "ux": ux,
        "stack_profile": stack_profile,
    }


def docs_are_in_canonical_dir(doc_paths: dict[str, list[Path]], root: Path | None = None) -> bool:
    root = root or project_root()
    canonical = canonical_source_docs_dir(root).resolve()
    chosen = [paths[0] for key, paths in doc_paths.items() if key in {"instructions", "checklist", "guide"} and len(paths) == 1]
    if not chosen:
        return False
    return all(canonical == p.resolve().parent or canonical in p.resolve().parents for p in chosen)


def registry_path() -> Path:
    return tasks_dir() / "registry.json"


def runtime_state_path() -> Path:
    return tasks_dir() / "runtime-state.json"


def ledger_path() -> Path:
    return tasks_dir() / "ledger.jsonl"


def bash_ledger_path() -> Path:
    # Runtime-only Bash observability. This file is intentionally ignored by git
    # so Claude Code PostToolUse Bash hooks cannot dirty the worktree after a
    # closer commit/push. Non-Bash lifecycle events still use ledger.jsonl.
    return tasks_dir() / "bash-ledger.jsonl"



def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def hook_error_log_path() -> Path:
    """Single place where hooks record exceptions.

    Read by the SessionStart hook so users see stale errors on the first turn.
    """
    return state_dir() / "hook-errors.log"


def log_hook_error(hook_name: str, exc: BaseException) -> None:
    """Append a hook exception to orchestrator-state/hook-errors.log.

    Never raises — if even the logging fails we swallow it (hooks must not
    block the pipeline). The intent is that silent-pass is replaced with a
    visible, auditable trail.
    """
    try:
        path = hook_error_log_path()
        ensure_parent(path)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(
                f"[{now_iso()}] {hook_name}: {type(exc).__name__}: {exc}\n"
            )
            fh.write("".join(traceback.format_exception(exc)))
            fh.write("\n---\n")
    except Exception:
        pass


# Reentrancy counter for file_lock: maps absolute lock-path string → depth.
# fcntl.flock is NOT reentrant across file descriptors in the same process
# (Linux/macOS), so without this counter `with file_lock(p):` nested inside
# another `with file_lock(p):` (e.g. hook → save_registry → write_json)
# deadlocks against itself. Hooks are single-threaded per invocation, so a
# plain dict is sufficient.
_LOCK_DEPTH: dict[str, int] = {}


@contextlib.contextmanager
def file_lock(path: Path, shared: bool = False) -> Iterator[None]:
    """Best-effort, **reentrant** file lock around mutations of JSON state files.

    Two SubagentStop hooks running in parallel (e.g. validator + tester both
    finishing at once) would otherwise race on registry.json. We take an
    exclusive lock on a sidecar `.lock` file, which is portable and does not
    require the target file to exist yet.

    Reentrancy: nested `with file_lock(p):` calls in the same process are
    cheap — only the outermost call performs the actual `flock`. This avoids
    the latent self-deadlock when the hook holds the registry lock and then
    `save_registry → write_json` tries to re-acquire it.

    On Windows (no fcntl) the lock becomes a no-op — hooks continue working,
    but under high concurrency there is a small race window. The framework is
    designed for POSIX developer machines where fcntl is available.
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    ensure_parent(lock_path)
    if not _HAS_FCNTL:
        # Touch the lock file so it exists, but skip actual locking.
        lock_path.touch(exist_ok=True)
        yield
        return

    key = str(lock_path.resolve())
    depth = _LOCK_DEPTH.get(key, 0)
    if depth > 0:
        # We already hold the lock in this process — just bump the counter.
        _LOCK_DEPTH[key] = depth + 1
        try:
            yield
        finally:
            _LOCK_DEPTH[key] -= 1
            if _LOCK_DEPTH[key] <= 0:
                _LOCK_DEPTH.pop(key, None)
        return

    fh = open(lock_path, "a+")
    try:
        mode = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
        fcntl.flock(fh.fileno(), mode)
        _LOCK_DEPTH[key] = 1
        try:
            yield
        finally:
            _LOCK_DEPTH[key] -= 1
            if _LOCK_DEPTH[key] <= 0:
                _LOCK_DEPTH.pop(key, None)
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    finally:
        fh.close()


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default


def write_text(path: Path, content: str) -> None:
    """Atomically write UTF-8 text with the same lock policy as JSON.

    Handoffs, task-packs, evidence summaries and Markdown views may be
    written while several DAG terminals are active. A sidecar lock plus
    temp-file/replace prevents partial writes and interleaving.
    """
    ensure_parent(path)
    with file_lock(path):
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)


def read_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    ensure_parent(path)
    with file_lock(path):
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        tmp.replace(path)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    ensure_parent(path)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with file_lock(path):
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root()).as_posix()
    except Exception:
        return path.as_posix()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def discover_markdown_files(root: Path | None = None) -> list[Path]:
    root = root or project_root()
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_SCAN_DIRS and not d.startswith(".cache")]
        for name in filenames:
            if name.lower().endswith(".md"):
                found.append(Path(dirpath) / name)
    return sorted(found)


def discover_source_docs(root: Path | None = None) -> dict[str, Any]:
    """Discover ONLY the active source-of-truth set.

    Canonical runtime docs are: instrucciones, technical guide, implementation
    checklist, optional UX_CONTRACT.md and optional STACK_PROFILE.yaml. If
    ``docs/source-of-truth`` exists, it is the only place inspected. This
    prevents accidental fallback to ``docs/product-baseline`` or ``docs/templates`` and
    avoids building the wrong app.
    """
    root = root or project_root()
    canonical_dir = canonical_source_docs_dir(root)
    if canonical_dir.exists():
        return scan_source_doc_candidates(canonical_dir)
    return {"instructions": [], "checklist": [], "guide": []}


def extract_headings(text: str) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if line.startswith("#"):
            m = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
            if m:
                headings.append({"level": len(m.group(1)), "title": m.group(2), "line": idx})
    return headings


def extract_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        m = CHECKBOX_RE.match(line)
        if m:
            items.append(m.group(1).strip())
    if items:
        return items
    for line in lines:
        m = BULLET_RE.match(line)
        if m:
            items.append(m.group(1).strip())
    return items


def phase_headings(headings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return canonical phase headings only.

    Uses the shallowest markdown level containing real "Phase N" headings.
    This keeps top-level phases while ignoring nested helpers such as
    ``## Phase 2 canonical slices`` or pre-gate text.
    """
    matches = [h for h in headings if PHASE_RE.match(h["title"])]
    if not matches:
        return []
    min_level = min(h.get("level", 99) for h in matches)
    return [h for h in matches if h.get("level") == min_level]


def slice_by_lines(text: str, start_line: int, end_line: int | None = None) -> list[str]:
    lines = text.splitlines()
    start_idx = max(start_line - 1, 0)
    end_idx = end_line - 1 if end_line is not None else len(lines)
    return lines[start_idx:end_idx]


def section_headings(headings: list[dict[str, Any]], start: dict[str, Any], end_line: int | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for h in headings:
        if h["line"] <= start["line"]:
            continue
        if end_line is not None and h["line"] >= end_line:
            continue
        if h["level"] > start["level"]:
            result.append(h)
    return result


def path_matches_patterns(path: Path | str, patterns: Iterable[str]) -> bool:
    path_str = relpath(Path(path)) if not isinstance(path, str) else path
    path_str = path_str.lstrip("./")
    if not list(patterns):
        return True
    for raw in patterns:
        pattern = raw.lstrip("./")
        if fnmatch.fnmatch(path_str, pattern):
            return True
    return False


def load_registry() -> dict[str, Any]:
    return read_json(registry_path(), {"generated_at": None, "project_prefix": None, "phase_order": [], "phases": [], "tasks": []})


def save_registry(data: dict[str, Any]) -> None:
    write_json(registry_path(), data)


def load_runtime_state() -> dict[str, Any]:
    """Read runtime-state.json with DAG-only defaults and a small schema.

    Runtime state is scheduler/support metadata, not task identity. Worker
    identity comes from CLAUDE_ACTIVE_TASK_ID + CLAUDE_TASK_PACK. Unknown keys
    from older installs are dropped when the state is loaded and saved again.
    """
    raw_state = read_json(runtime_state_path(), {})
    allowed_keys = {
        "generated_at",
        "last_worker",
        "last_event",
        "last_journey_verified",
        "pending_journey_verifications",
        "spawn_budget",
        "spawns_in_current_slice",
        "open_followups",
        "last_trailer",
        "last_stop_at",
        "last_followup_id",
        "last_claimed_task_id",
        "last_claimed_phase_id",
        "next_ready_task_id",
        "next_ready_phase_id",
    }
    state = {k: v for k, v in raw_state.items() if k in allowed_keys}
    defaults = {
        "generated_at": None,
        "last_worker": None,
        "last_event": None,
        "pending_journey_verifications": [],
        "last_journey_verified": None,
        "spawn_budget": DEFAULT_SPAWN_BUDGET,
        "spawns_in_current_slice": {},
        "open_followups": [],
    }
    for key, default in defaults.items():
        state.setdefault(key, default)
    if not isinstance(state.get("pending_journey_verifications"), list):
        state["pending_journey_verifications"] = []
    if not isinstance(state.get("spawns_in_current_slice"), dict):
        state["spawns_in_current_slice"] = {}
    if not isinstance(state.get("open_followups"), list):
        state["open_followups"] = []
    return state




def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = re.split(r"[,;\s]+", str(value))
    out: list[str] = []
    for item in raw_items:
        token = str(item or "").strip().strip("`")
        if not token or token.lower() in {"-", "—", "none", "n/a", "na", "null"}:
            continue
        if token not in out:
            out.append(token)
    return out


def task_journey_refs(task: dict[str, Any]) -> list[str]:
    """Collect all journey references that can make a task subject to a gate.

    The Coverage Registry normally provides ``journey_refs``. The extra fields
    are supported for manual follow-up tasks and generated YAML.
    """
    refs: list[str] = []
    for key in ("journey_refs", "journey_refs_raw", "depends_on_journeys", "journey_gate_refs"):
        for item in _as_list(task.get(key)):
            if re.fullmatch(r"J\d+", item, re.I) and item.upper() not in refs:
                refs.append(item.upper())
    # Origins often look like §3.7#J101. Use them only as a fallback.
    for key in ("origin_instr", "source_ref", "notes"):
        raw = task.get(key)
        if isinstance(raw, dict):
            raw = json.dumps(raw, ensure_ascii=False)
        for item in re.findall(r"\bJ\d+\b", str(raw or ""), re.I):
            jid = item.upper()
            if jid not in refs:
                refs.append(jid)
    return refs


def pending_journey_blockers_for_task(task: dict[str, Any], runtime: dict[str, Any] | None = None) -> list[str]:
    """Return pending journeys that should defer/deny this task.

    DAG-only journey gate: pending journey verifications defer only tasks that
    explicitly reference those journeys. There is no alternate journey-gate mode.
    """
    runtime = runtime or load_runtime_state()
    pending = [str(j).strip().upper() for j in (runtime.get("pending_journey_verifications") or []) if str(j).strip()]
    if not pending:
        return []
    refs = set(task_journey_refs(task))
    return [jid for jid in pending if jid in refs]


def journey_gate_blocks_task(task: dict[str, Any], runtime: dict[str, Any] | None = None) -> bool:
    return bool(pending_journey_blockers_for_task(task, runtime))

def save_runtime_state(data: dict[str, Any]) -> None:
    write_json(runtime_state_path(), data)




def blocking_open_followups(runtime: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return unresolved follow-up proposals that must block new DAG work.

    Validator/tester may discover production-relevant work that is outside the
    current slice. Such findings are first written as proposal YAML under
    ``orchestrator-state/tasks/follow-ups/`` and recorded in runtime-state.
    Critical/high/blocker proposals must be promoted into a real DAG task or
    waived before a closer can mark the origin done or a new wave can start.
    """
    runtime = runtime or load_runtime_state()
    blocking = []
    for item in runtime.get("open_followups", []) or []:
        status = str(item.get("status") or "proposed").strip().lower()
        severity = str(item.get("severity") or "medium").strip().lower()
        if status == "proposed" and severity in {"blocker", "critical", "high", "alto", "critico", "crítico"}:
            blocking.append(item)
    return blocking


def blocking_followups_for_task(task_id: str | None, runtime: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if not task_id:
        return []
    return [item for item in blocking_open_followups(runtime) if str(item.get("origin_task_id") or "") == str(task_id)]

def bump_spawn_count(task_id: str | None, agent_type: str | None) -> int:
    """Increment the spawn counter for ``task_id`` and return the new value.

    Idempotent in spirit (each call increments by 1 regardless of agent_type),
    so the caller — typically the SubagentStop hook — does NOT need to know
    whether the agent was info-only or lifecycle-owning. Both count toward
    the slice budget, because the budget is about CONTEXT consumption, not
    state ownership.

    DAG semantics: counters are keyed by explicit TASK_ID. Several task counters
    may coexist safely while independent slices run in parallel.

    Returns 0 when ``task_id`` is None (defensive — never raises).
    """
    if not task_id:
        return 0
    with file_lock(runtime_state_path()):
        state = load_runtime_state()
        counts = state.get("spawns_in_current_slice") or {}
        if not isinstance(counts, dict):
            counts = {}
        # DAG worker terminals set CLAUDE_ACTIVE_TASK_ID, so several task
        # counters may coexist safely while independent slices run in parallel.
        # Without CLAUDE_ACTIVE_TASK_ID, callers should avoid slice-specific use.
        new_count = int(counts.get(task_id, 0)) + 1
        counts[task_id] = new_count
        if agent_type:
            agent_key = f"agent:{agent_type}"
            counts[agent_key] = int(counts.get(agent_key, 0)) + 1
        state["spawns_in_current_slice"] = counts
        save_runtime_state(state)
    return new_count


def get_spawn_count(task_id: str | None) -> int:
    """Read-only counterpart to bump_spawn_count. Returns 0 if not tracked."""
    if not task_id:
        return 0
    counts = load_runtime_state().get("spawns_in_current_slice") or {}
    if not isinstance(counts, dict):
        return 0
    return int(counts.get(task_id, 0))


def get_spawn_budget() -> int:
    """Configured spawn budget per slice (default 20, settable via runtime-state)."""
    state = load_runtime_state()
    try:
        return int(state.get("spawn_budget", DEFAULT_SPAWN_BUDGET))
    except (TypeError, ValueError):
        return DEFAULT_SPAWN_BUDGET


def reset_spawn_counter(task_id: str | None = None) -> None:
    """Clear the spawn counter. Called by the planner when starting a new slice
    (so the budget visibly resets to 0/20 for the new task)."""
    with file_lock(runtime_state_path()):
        state = load_runtime_state()
        if task_id:
            counts = state.get("spawns_in_current_slice") or {}
            if isinstance(counts, dict):
                # Remove only entries scoped to this task (leave agent counters
                # for the next slice cycle to overwrite naturally).
                counts = {k: v for k, v in counts.items() if k != task_id and not k.startswith("agent:")}
                state["spawns_in_current_slice"] = counts
        else:
            state["spawns_in_current_slice"] = {}
        save_runtime_state(state)



def registry_is_explicit_dag(registry: dict[str, Any] | None = None) -> bool:
    try:
        registry = registry if registry is not None else load_registry()
        return ((registry or {}).get("task_dag") or {}).get("mode") == "explicit_dag"
    except Exception:
        return False


def dag_worker_task_id() -> str | None:
    """Return the explicit per-terminal TASK_ID for DAG workers, if present."""
    raw = (os.environ.get("CLAUDE_ACTIVE_TASK_ID") or os.environ.get("CLAUDE_TASK_ID") or "").strip()
    if not raw or raw.lower() in {"none", "null", "n/a", "na", "-", "—"}:
        return None
    return raw


def effective_worker_task_id() -> str | None:
    """Return the explicit DAG worker TASK_ID from the terminal environment.

    Production is DAG-only: this function never reads singleton task/phase
    files and never infers a task from runtime-state.
    """
    return dag_worker_task_id()


def find_task(registry: dict[str, Any], task_id: str | None) -> dict[str, Any] | None:
    if not task_id:
        return None
    for task in registry.get("tasks", []):
        if task.get("id") == task_id:
            return task
    return None


def find_phase(registry: dict[str, Any], phase_id: str | None) -> dict[str, Any] | None:
    if not phase_id:
        return None
    for phase in registry.get("phases", []):
        if phase.get("id") == phase_id:
            return phase
    return None


def tasks_by_phase(registry: dict[str, Any], phase_id: str) -> list[dict[str, Any]]:
    return [t for t in registry.get("tasks", []) if t.get("phase_id") == phase_id]



def split_metadata_cell(value: Any) -> list[str]:
    """Split Coverage Registry metadata cells such as Conflict groups/Write set.

    These cells are scheduler hints, not prose. We split on separators that are
    safe for paths and identifiers, keep glob characters, remove markdown noise,
    and drop neutral values such as "—" or "read-only".
    """
    if isinstance(value, list):
        raw_items = value
    else:
        text = str(value or "").replace("`", "").replace("\\|", "|").strip()
        raw_items = re.split(r"[,;\n]", text)
    items: list[str] = []
    for raw in raw_items:
        item = str(raw or "").replace("`", "").strip()
        if not item or item.lower() in NEUTRAL_CONFLICT_VALUES:
            continue
        if item not in items:
            items.append(item)
    return items


def _normalise_conflict_group(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"\s+", "-", value)
    return value


def task_conflict_groups(task: dict[str, Any]) -> list[str]:
    values = task.get("conflict_groups") or task.get("conflict_group") or []
    return [_normalise_conflict_group(v) for v in split_metadata_cell(values)]


def task_write_set(task: dict[str, Any]) -> list[str]:
    values = task.get("write_set") or task.get("expected_files_touched") or []
    cleaned: list[str] = []
    for item in split_metadata_cell(values):
        normal = item.strip().lstrip("./")
        if normal and normal not in cleaned:
            cleaned.append(normal)
    return cleaned


def _strip_glob_suffix(pattern: str) -> str:
    pattern = pattern.strip().lstrip("./")
    for suffix in ("/**", "/*"):
        if pattern.endswith(suffix):
            return pattern[:-len(suffix)]
    return pattern


def write_patterns_conflict(left: str, right: str) -> bool:
    """Return True when two declared write-set patterns may touch same files."""
    a = left.strip().lstrip("./")
    b = right.strip().lstrip("./")
    if not a or not b:
        return False
    if a == b:
        return True
    # Glob relation in either direction.
    if fnmatch.fnmatch(a, b) or fnmatch.fnmatch(b, a):
        return True
    # Directory-prefix relation for common path patterns like lib/core/**.
    ap = _strip_glob_suffix(a).rstrip("/")
    bp = _strip_glob_suffix(b).rstrip("/")
    if ap and bp and (ap.startswith(bp + "/") or bp.startswith(ap + "/")):
        return True
    return False


def heuristic_conflict_groups(task: dict[str, Any]) -> list[str]:
    """Fallback groups for rows that do not declare conflict metadata."""
    title = str(task.get("title") or "")
    out: list[str] = []
    m = re.search(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+([^\s`|,;]+)", title, re.I)
    if m:
        path = m.group(2)
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3 and parts[0] == "api":
            out.append("api:/" + "/".join(parts[:3]))
        elif len(parts) >= 2:
            out.append("api:/" + "/".join(parts[:2]))
        else:
            out.append("api:" + path)
    if re.search(r"\b000\d+_.*\.py\b", title):
        out.append("db:migration")
    if "provider" in title.lower():
        out.append("provider:" + re.sub(r"\W+", "-", title.lower())[:32])
    return [_normalise_conflict_group(x) for x in out]


def task_conflict_reasons(task: dict[str, Any], other: dict[str, Any]) -> list[str]:
    """Explain why two tasks should not run in the same DAG wave."""
    reasons: list[str] = []
    groups = set(task_conflict_groups(task))
    other_groups = set(task_conflict_groups(other))
    common_groups = sorted(groups & other_groups)
    if common_groups:
        reasons.append("conflict_groups=" + ",".join(common_groups))

    writes = task_write_set(task)
    other_writes = task_write_set(other)
    common_writes: list[str] = []
    for a in writes:
        for b in other_writes:
            if write_patterns_conflict(a, b):
                pair = a if a == b else f"{a}<->{b}"
                if pair not in common_writes:
                    common_writes.append(pair)
    if common_writes:
        reasons.append("write_set=" + ",".join(common_writes[:5]))

    # Heuristic fallback only when both tasks lack explicit metadata; explicit
    # metadata is authoritative and avoids over-serialising a well-designed DAG.
    if not groups and not other_groups and not writes and not other_writes:
        h_common = sorted(set(heuristic_conflict_groups(task)) & set(heuristic_conflict_groups(other)))
        if h_common:
            reasons.append("heuristic=" + ",".join(h_common))
    return reasons


def active_conflict_blockers(registry: dict[str, Any], task: dict[str, Any], *, active_statuses: set[str] | None = None) -> list[dict[str, Any]]:
    """Return DAG tasks that conflict with ``task`` under declared metadata.

    Used by claim_task.py as a final safety net. Even if a user manually starts
    two terminals without going through /next-wave, the second claim is denied
    when the slices share a conflict group or write-set path.
    """
    active_statuses = active_statuses or SCHEDULER_ACTIVE_STATUSES
    blockers: list[dict[str, Any]] = []
    tid = task.get("id")
    for other in registry.get("tasks", []) or []:
        if other.get("id") == tid:
            continue
        status = other.get("status")
        is_blocker = status in active_statuses or (status == "blocked" and task_is_ready(registry, other))
        if not is_blocker:
            continue
        reasons = task_conflict_reasons(task, other)
        if reasons:
            blockers.append({"task_id": other.get("id"), "status": other.get("status"), "reasons": reasons})
    return blockers


def task_is_ready(registry: dict[str, Any], task: dict[str, Any]) -> bool:
    deps = task.get("depends_on", [])
    done_ids = {t["id"] for t in registry.get("tasks", []) if t.get("status") == "done"}
    return all(dep in done_ids for dep in deps)


def refresh_phase_statuses(registry: dict[str, Any]) -> dict[str, Any]:
    for phase in registry.get("phases", []):
        phase_tasks = tasks_by_phase(registry, phase["id"])
        statuses = {t.get("status") for t in phase_tasks}
        if phase_tasks and all(t.get("status") == "done" for t in phase_tasks):
            phase["status"] = "complete"
        elif "claimed" in statuses or "in_progress" in statuses or "review_pending" in statuses or "test_pending" in statuses or "qa_pending" in statuses or "needs_debug" in statuses:
            phase["status"] = "active"
        elif any(task_is_ready(registry, t) and t.get("status") in {"planned", "blocked", "ready"} for t in phase_tasks):
            phase["status"] = "ready"
        elif phase_tasks:
            phase["status"] = "blocked"
        else:
            phase["status"] = "empty"
    return registry


def promote_ready_tasks(registry: dict[str, Any]) -> dict[str, Any]:
    done_ids = {t["id"] for t in registry.get("tasks", []) if t.get("status") == "done"}
    for task in registry.get("tasks", []):
        status = task.get("status")
        deps_ready = all(dep in done_ids for dep in task.get("depends_on", []))
        if not deps_ready:
            continue
        if status in {"planned", "ready"}:
            task["status"] = "ready"
            continue
        if status != "blocked":
            continue

        last_blocker = task.get("last_blocker")
        conflict_block = (
            task.get("blocked_reason") == "conflict_with_worker_task"
            or (isinstance(last_blocker, dict) and last_blocker.get("type") == "conflict_with_worker_task")
        )
        if conflict_block:
            blockers = active_conflict_blockers(registry, task)
            if blockers:
                task["blocked_by"] = [str(item.get("task_id")) for item in blockers if item.get("task_id")]
                task["last_blocker"] = {"type": "conflict_with_worker_task", "blockers": blockers, "ts": now_iso()}
                continue
            task.pop("blocked_reason", None)
            task.pop("blocked_by", None)
            task.pop("last_blocker", None)
            task["status"] = "ready"
            continue

        explicit_block = bool(last_blocker)
        if not explicit_block:
            task["status"] = "ready"
    return refresh_phase_statuses(registry)


def choose_next_scheduler_task(registry: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    registry = promote_ready_tasks(registry)
    phase_order = registry.get("phase_order", [])
    phases = {p["id"]: p for p in registry.get("phases", [])}
    for phase_id in phase_order:
        phase = phases.get(phase_id)
        if not phase:
            continue
        phase_tasks = tasks_by_phase(registry, phase_id)
        if all(t.get("status") == "done" for t in phase_tasks) and phase_tasks:
            continue
        for task in phase_tasks:
            if task.get("status") == "ready":
                return phase, task
        for task in phase_tasks:
            if task.get("status") in {"claimed", "in_progress", "needs_debug", "blocked"}:
                return phase, task
    return None, None


def sync_runtime_state_from_registry(registry: dict[str, Any]) -> None:
    """Persist runtime housekeeping after registry status changes.

    DAG-only mode has no global DAG task/implicit selector. This function keeps
    runtime metadata fresh without choosing work for terminals.
    """
    state = load_runtime_state()
    state["generated_at"] = now_iso()
    state.setdefault("last_event", "registry_synced")
    save_runtime_state(state)


def update_task_status(task_id: str, status: str, agent: str | None = None, note: str | None = None) -> None:
    with file_lock(registry_path()):
        registry = load_registry()
        task = find_task(registry, task_id)
        if not task:
            return
        task["status"] = status
        if agent:
            task["last_updated_by"] = agent
        if note:
            task["last_note"] = note
        # Write registry + runtime-state atomically under the same lock window.
        save_registry(promote_ready_tasks(registry))
        sync_runtime_state_from_registry(load_registry())


def mark_task_blocked(task_id: str, reason: str, agent: str | None = None) -> None:
    """Mark a task as blocked with a reason and auto-skip it in the scheduler queue.

    Used by the debugger when it hits the max-retry cap, and by any worker
    that raises a non-recoverable condition. Preserves the reason in
    `last_blocker` so the next planner run can surface it.
    """
    with file_lock(registry_path()):
        registry = load_registry()
        task = find_task(registry, task_id)
        if not task:
            return
        task["status"] = "blocked"
        task["last_blocker"] = {"reason": reason, "agent": agent, "at": now_iso()}
        if agent:
            task["last_updated_by"] = agent
        save_registry(promote_ready_tasks(registry))
        sync_runtime_state_from_registry(load_registry())


def has_unresolved_doc_discrepancies() -> tuple[bool, list[str]]:
    """Scan orchestrator-state/memory/official-doc-notes/ for unresolved notes.

    A note is considered unresolved if its body does not contain a line
    starting with `RESOLVED` (canonical form: `RESOLVED: <how>`; date-prefixed form `RESOLVED 2026-...` is accepted). The PreToolUse
    docs-discrepancy hook uses this to warn on Write/Edit while there is an
    open reconciliation pending.
    """
    notes_dir = memory_dir() / "official-doc-notes"
    if not notes_dir.is_dir():
        return False, []
    unresolved: list[str] = []
    for note in sorted(notes_dir.glob("*.md")):
        try:
            text = note.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if not has_resolved_doc_discrepancy_marker(text):
            unresolved.append(relpath(note))
    return (len(unresolved) > 0), unresolved




DOC_DISCREPANCY_RESOLVED_RE = re.compile(r"(?im)^\s*RESOLVED(?:\s*:|\s+\d{4}-\d{2}-\d{2}\b|\s+[-–—])")


def has_resolved_doc_discrepancy_marker(text: str) -> bool:
    """Return True when an official-doc discrepancy note is marked resolved.

    Canonical notes should use `RESOLVED: <how>`, but older agents sometimes
    wrote `RESOLVED 2026-05-11 ...`. Accept that date form, plus
    `RESOLVED - ...`, so SessionStart/PreToolUse do not keep warning after the
    code has actually been reconciled. A bare `RESOLVED` without detail is not
    accepted; every agent should leave an explanation.
    """
    return bool(DOC_DISCREPANCY_RESOLVED_RE.search(text or ""))


def run_commands(commands: list[str], cwd: Path | None = None, timeout: int = 900) -> list[dict[str, Any]]:
    cwd = cwd or workspace_root()
    results: list[dict[str, Any]] = []
    for cmd in commands:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        results.append(
            {
                "command": cmd,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
    return results


# ---------------------------------------------------------------------------
# Journey state helpers (added by journey-verification feature)
#
# Estos helpers son aditivos: no tocan ninguna lógica preexistente. Si la
# matriz §3.5 no existe en instrucciones.md (proyecto pre-matriz), todas
# estas funciones devuelven listas/dicts vacíos sin error.
# ---------------------------------------------------------------------------


def journey_handoffs_dir() -> Path:
    """Directorio donde /verify-journey escribe los handoffs por journey."""
    return tasks_dir() / "journey-handoffs"


def journey_evidence_dir() -> Path:
    """Directorio donde /verify-journey deja screenshots y logs."""
    return tasks_dir() / "evidence" / "journeys"


def load_journeys(registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Lee journeys[] del registry. Devuelve [] si la clave no existe
    (back-compat con proyectos pre-matriz)."""
    if registry is None:
        registry = load_registry()
    return registry.get("journeys", []) or []


def find_journey(registry: dict[str, Any], journey_id: str | None) -> dict[str, Any] | None:
    if not journey_id:
        return None
    for j in load_journeys(registry):
        if j.get("id") == journey_id:
            return j
    return None


def _journey_task_statuses(registry: dict[str, Any]) -> dict[str, str]:
    return {str(t.get("id")): str(t.get("status") or "") for t in registry.get("tasks", []) or [] if t.get("id")}


def journey_completion_task_ids(registry: dict[str, Any], journey: dict[str, Any]) -> list[str]:
    """Return the DAG terminal task IDs for one journey.

    In a DAG, a journey may have several terminal nodes. The robust completion
    frontier is the set of journey tasks with no outgoing dependency to another
    task in the same journey.
    """
    task_ids = [str(t) for t in (journey.get("task_ids") or []) if t]
    if not task_ids:
        return []
    task_set = set(task_ids)
    dag = registry.get("task_dag") or {}
    adjacency = dag.get("adjacency_list") or {}
    frontier: list[str] = []
    for tid in task_ids:
        successors = [str(x) for x in (adjacency.get(tid) or [])]
        if not any(s in task_set for s in successors):
            frontier.append(tid)
    if frontier:
        return frontier
    # Fallback for registries without task_dag metadata.
    return [task_ids[-1]]


def journeys_closing_at_task(registry: dict[str, Any], task_id: str) -> list[str]:
    """Return JOURNEY_IDs made ready for verification by ``task_id`` closing.

    The test is status-based, not positional. A task closes a journey when:

    - it belongs to the journey;
    - the journey is not already verified/waived;
    - every other task in that journey is already ``done``.

    This works for task lists, explicit DAG ranges, and unordered
    Journey Matrix cells. It also avoids the classic ``task_ids[-1]`` bug where
    the wrong node was treated as the journey closer.
    """
    closing: list[str] = []
    if not task_id:
        return closing
    statuses = _journey_task_statuses(registry)
    for j in load_journeys(registry):
        status = str(j.get("verification_status") or "pending").lower()
        if status in {"verified", "waived"}:
            continue
        task_ids = [str(t) for t in (j.get("task_ids") or []) if t]
        if task_id not in task_ids:
            continue
        unresolved = [tid for tid in task_ids if tid != task_id and statuses.get(tid) != "done"]
        if unresolved:
            continue
        jid = j.get("id")
        if jid and jid not in closing:
            closing.append(str(jid))
    return closing


def get_pending_journey_verifications() -> list[str]:
    """Lee runtime-state.pending_journey_verifications. [] si no existe."""
    state = load_runtime_state()
    pending = state.get("pending_journey_verifications", [])
    if not isinstance(pending, list):
        return []
    return [str(j) for j in pending if j]


def add_pending_journey_verification(journey_id: str) -> None:
    """Añade un JOURNEY_ID a pending_journey_verifications bajo file lock.
    Idempotente: si ya está, no hace nada."""
    if not journey_id:
        return
    with file_lock(runtime_state_path()):
        state = load_runtime_state()
        pending = list(state.get("pending_journey_verifications", []) or [])
        if journey_id not in pending:
            pending.append(journey_id)
        state["pending_journey_verifications"] = pending
        state["last_event"] = "journey_pending_verify"
        save_runtime_state(state)


def remove_pending_journey_verification(journey_id: str, mark_verified: bool = True) -> None:
    """Quita un JOURNEY_ID de pending_journey_verifications.
    Si mark_verified=True (default), marca el journey como verified en registry.journeys[].

    Lock order convention (project-wide): registry FIRST, runtime-state SECOND.
    Inverting this opens a deadlock window with main() in hook_capture_subagent_stop,
    which already holds registry while updating runtime-state.
    """
    if not journey_id:
        return
    with file_lock(registry_path()):
        if mark_verified:
            registry = load_registry()
            for j in (registry.get("journeys", []) or []):
                if j.get("id") == journey_id:
                    j["verification_status"] = "verified"
                    j["verified_at"] = now_iso()
            save_registry(registry)
        with file_lock(runtime_state_path()):
            state = load_runtime_state()
            pending = [j for j in (state.get("pending_journey_verifications", []) or []) if j != journey_id]
            state["pending_journey_verifications"] = pending
            if mark_verified:
                state["last_journey_verified"] = journey_id
                state["last_event"] = "journey_verified"
            save_runtime_state(state)


def waive_journey_verification(journey_id: str, reason: str) -> None:
    """Marca un journey como waived (verificación saltada con motivo explícito).
    Quita de pending y marca en registry.

    Lock order: registry first, runtime-state second (project-wide convention).
    """
    if not journey_id:
        return
    with file_lock(registry_path()):
        registry = load_registry()
        for j in (registry.get("journeys", []) or []):
            if j.get("id") == journey_id:
                j["verification_status"] = "waived"
                j["waiver_reason"] = reason or "no_reason_given"
                j["verified_at"] = now_iso()
        save_registry(registry)
        with file_lock(runtime_state_path()):
            state = load_runtime_state()
            pending = [j for j in (state.get("pending_journey_verifications", []) or []) if j != journey_id]
            state["pending_journey_verifications"] = pending
            state["last_event"] = "journey_waived"
            save_runtime_state(state)

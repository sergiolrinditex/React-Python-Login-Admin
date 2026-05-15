"""DAG task orchestration contract.

Pins the backward-compatible behavior:
- no `Depends on` column => missing_dependency_column DAG dependency diagnostic;
- `Depends on` column => explicit DAG roots can run in parallel;
- derived adjacency matrix and waves are deterministic;
- per-terminal CLAUDE_ACTIVE_TASK_ID protects hook accounting in parallel workers;
- claim_task atomically claims a ready task.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

_BIN = Path(__file__).resolve().parent.parent
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

import bootstrap_source_of_truth as boot  # noqa: E402


class _Sandbox:
    def __init__(self, root: Path):
        self.root = root
        self._prev_project = None
        self._prev_active = None

    def __enter__(self):
        self._prev_project = os.environ.get("CLAUDE_PROJECT_DIR")
        self._prev_active = os.environ.get("CLAUDE_ACTIVE_TASK_ID")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.root)
        os.environ.pop("CLAUDE_ACTIVE_TASK_ID", None)
        import common
        common._LOCK_DEPTH.clear()
        return self

    def __exit__(self, *exc):
        if self._prev_project is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = self._prev_project
        if self._prev_active is None:
            os.environ.pop("CLAUDE_ACTIVE_TASK_ID", None)
        else:
            os.environ["CLAUDE_ACTIVE_TASK_ID"] = self._prev_active


def _setup_root():
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    (root / "orchestrator-state" / "tasks").mkdir(parents=True)
    (root / "orchestrator-state" / "memory").mkdir(parents=True)
    return root, td


def _dag_checklist() -> str:
    return """# App Implementation Checklist

## Coverage Registry

| Slice ID | Target | Step | Depends on | Verify mínimo |
|---|---|---|---|---|
| P00-S01-T001 | A | Step 0.1 | — | test A |
| P00-S01-T002 | B | Step 0.1 | — | test B |
| P00-S02-T001 | C | Step 0.2 | P00-S01-T001, P00-S01-T002 | test C |

# Phase 0 — Test phase

## Step 0.1 — Roots
- roots exist

## Step 0.2 — Join
- join exists
"""


def _missing_dependency_column_checklist() -> str:
    return """# App Implementation Checklist

## Coverage Registry

| Slice ID | Target | Step | Verify mínimo |
|---|---|---|---|
| P00-S01-T001 | A | Step 0.1 | test A |
| P00-S01-T002 | B | Step 0.1 | test B |
| P00-S02-T001 | C | Step 0.2 | test C |

# Phase 0 — Test phase

## Step 0.1 — Roots
- roots exist

## Step 0.2 — Join
- join exists
"""


class BootstrapDagModeTests(unittest.TestCase):

    def test_explicit_depends_on_column_enables_parallel_roots(self):
        phases, tasks = boot.build_phases_and_tasks(Path("APP_IMPLEMENTATION_CHECKLIST.md"), _dag_checklist())
        self.assertEqual([t["id"] for t in tasks], ["P00-S01-T001", "P00-S01-T002", "P00-S02-T001"])
        by_id = {t["id"]: t for t in tasks}
        self.assertEqual(by_id["P00-S01-T001"]["status"], "ready")
        self.assertEqual(by_id["P00-S01-T002"]["status"], "ready")
        self.assertEqual(by_id["P00-S02-T001"]["status"], "blocked")
        self.assertEqual(by_id["P00-S02-T001"]["depends_on"], ["P00-S01-T001", "P00-S01-T002"])
        self.assertEqual(by_id["P00-S02-T001"].get("dependency_mode"), "explicit_dag")
        self.assertEqual(phases[0].get("_dag_errors"), [])

    def test_no_depends_on_column_reports_dag_error(self):
        phases, tasks = boot.build_phases_and_tasks(Path("APP_IMPLEMENTATION_CHECKLIST.md"), _missing_dependency_column_checklist())
        self.assertTrue(tasks, "rows may still be parsed for diagnostics")
        self.assertTrue(any("Dependency" in e or "dependency" in e for e in phases[0].get("_dag_errors", [])))


    def test_compact_step_refs_do_not_create_synthetic_duplicates(self):
        cl = """# App Implementation Checklist

## Coverage Registry

| Slice ID | Target | Phase | Step | Depends on | Verify mínimo |
|---|---|---|---|---|---|
| P00-S01-T001 | A | P00 | S01 | — | test A |
| P00-S01-T002 | B | P00 | P00-S01 | — | test B |
| P00-S02-T001 | C | P00 | 0.2 | P00-S01 | test C |

# Phase 0 — Test phase

## Step 0.1 — Roots
- roots exist

## Step 0.2 — Join
- join exists
"""
        _, tasks = boot.build_phases_and_tasks(Path("APP_IMPLEMENTATION_CHECKLIST.md"), cl)
        self.assertEqual([t["id"] for t in tasks], ["P00-S01-T001", "P00-S01-T002", "P00-S02-T001"])
        self.assertTrue(all("synthetic" not in " ".join(t.get("notes", [])) for t in tasks))
        self.assertEqual(tasks[2]["depends_on"], ["P00-S01-T001", "P00-S01-T002"])

    def test_task_dag_matrix_and_waves_are_derived(self):
        _, tasks = boot.build_phases_and_tasks(Path("APP_IMPLEMENTATION_CHECKLIST.md"), _dag_checklist())
        dag = boot.build_task_dag(tasks)
        self.assertEqual(dag["mode"], "explicit_dag")
        self.assertEqual(dag["edges"], [["P00-S01-T001", "P00-S02-T001"], ["P00-S01-T002", "P00-S02-T001"]])
        self.assertEqual(dag["topological_levels"], [["P00-S01-T001", "P00-S01-T002"], ["P00-S02-T001"]])
        i = dag["adjacency_index"]
        self.assertEqual(dag["adjacency_matrix"][i["P00-S01-T001"]][i["P00-S02-T001"]], 1)
        self.assertEqual(dag["adjacency_matrix"][i["P00-S01-T002"]][i["P00-S02-T001"]], 1)

    def test_dag_cycle_is_reported(self):
        tasks = [
            {"id": "P00-S01-T001", "depends_on": ["P00-S01-T002"]},
            {"id": "P00-S01-T002", "depends_on": ["P00-S01-T001"]},
        ]
        dag = boot.build_task_dag(tasks)
        self.assertTrue(any("cycle detected" in err for err in dag["errors"]))
        self.assertEqual(dag["topological_levels"], [])

    def test_step_ref_dependency_expands_to_all_step_tasks(self):
        cl = _dag_checklist().replace(
            "P00-S01-T001, P00-S01-T002 | test C",
            "P00-S01 | test C",
        )
        _, tasks = boot.build_phases_and_tasks(Path("APP_IMPLEMENTATION_CHECKLIST.md"), cl)
        by_id = {t["id"]: t for t in tasks}
        self.assertEqual(by_id["P00-S02-T001"]["depends_on"], ["P00-S01-T001", "P00-S01-T002"])


class DagRuntimeSafetyTests(unittest.TestCase):

    def _seed_registry(self, common):
        tasks = [
            {"id": "P00-S01-T001", "title": "A", "phase_id": "P00", "step_id": "P00-S01", "status": "ready", "depends_on": []},
            {"id": "P00-S01-T002", "title": "B", "phase_id": "P00", "step_id": "P00-S01", "status": "ready", "depends_on": []},
        ]
        common.save_registry({
            "generated_at": common.now_iso(),
            "project_prefix": "TEST",
            "phase_order": ["P00"],
            "phases": [{"id": "P00", "title": "P0", "status": "ready", "task_ids": [t["id"] for t in tasks]}],
            "tasks": tasks,
            "journeys": [],
            "task_dag": boot.build_task_dag(tasks),
        })
        common.save_runtime_state({
            "generated_at": common.now_iso(),
            "last_worker": None,
            "last_event": None,
            "pending_journey_verifications": [],
            "last_journey_verified": None,
            "spawn_budget": 20,
            "spawns_in_current_slice": {},
        })

    def test_claim_task_marks_ready_task_claimed_atomically(self):
        root, td = _setup_root()
        try:
            with _Sandbox(root):
                import common
                import claim_task
                self._seed_registry(common)
                ok, result = claim_task.claim_task("P00-S01-T002")
                self.assertTrue(ok)
                self.assertEqual(result["task"]["status"], "claimed")
                self.assertEqual(common.load_runtime_state()["last_claimed_task_id"], "P00-S01-T002")
                self.assertIsNone(common.effective_worker_task_id())
                self.assertFalse((root / "orchestrator-state/memory/removed implicit selector.json").exists())
                self.assertFalse((root / "orchestrator-state/memory/removed implicit selector").exists())

                ok2, result2 = claim_task.claim_task("P00-S01-T002")
                self.assertFalse(ok2)
                self.assertIn("already claimed", result2["error"])
        finally:
            td.cleanup()


    def test_claim_task_creates_per_task_pack_for_dag_worker(self):
        root, td = _setup_root()
        try:
            with _Sandbox(root):
                import common
                import claim_task
                self._seed_registry(common)
                ok, result = claim_task.claim_task("P00-S01-T002")
                self.assertTrue(ok)
                pack_rel = result["task"].get("task_pack_path")
                self.assertEqual(pack_rel, "orchestrator-state/tasks/task-packs/P00-S01-T002.md")
                pack = root / pack_rel
                self.assertTrue(pack.exists())
                body = pack.read_text(encoding="utf-8")
                self.assertIn("Minimal pack created by claim_task.py", body)
                self.assertIn("TASK_ID: P00-S01-T002", body)
                registry_task = {t["id"]: t for t in common.load_registry()["tasks"]}["P00-S01-T002"]
                self.assertEqual(registry_task.get("task_pack_path"), pack_rel)
        finally:
            td.cleanup()


    def test_join_task_stays_blocked_until_all_predecessors_done(self):
        root, td = _setup_root()
        try:
            with _Sandbox(root):
                import common
                tasks = [
                    {"id": "P00-S01-T001", "title": "A", "phase_id": "P00", "step_id": "P00-S01", "status": "done", "depends_on": []},
                    {"id": "P00-S01-T002", "title": "B", "phase_id": "P00", "step_id": "P00-S01", "status": "ready", "depends_on": []},
                    {"id": "P00-S02-T001", "title": "Join", "phase_id": "P00", "step_id": "P00-S02", "status": "blocked", "depends_on": ["P00-S01-T001", "P00-S01-T002"]},
                ]
                registry = {
                    "generated_at": common.now_iso(),
                    "project_prefix": "TEST",
                    "phase_order": ["P00"],
                    "phases": [{"id": "P00", "title": "P0", "status": "active", "task_ids": [t["id"] for t in tasks]}],
                    "tasks": tasks,
                    "journeys": [],
                    "task_dag": boot.build_task_dag(tasks),
                }
                promoted = common.promote_ready_tasks(registry)
                by_id = {t["id"]: t for t in promoted["tasks"]}
                self.assertEqual(by_id["P00-S02-T001"]["status"], "blocked")
                self.assertFalse(common.task_is_ready(promoted, by_id["P00-S02-T001"]))

                by_id["P00-S01-T002"]["status"] = "done"
                promoted = common.promote_ready_tasks(promoted)
                by_id = {t["id"]: t for t in promoted["tasks"]}
                self.assertEqual(by_id["P00-S02-T001"]["status"], "ready")
                self.assertTrue(common.task_is_ready(promoted, by_id["P00-S02-T001"]))
        finally:
            td.cleanup()

    def test_phase_status_treats_close_gate_states_as_active(self):
        root, td = _setup_root()
        try:
            with _Sandbox(root):
                import common
                for state in ("ready_for_close", "verified_pending_close"):
                    tasks = [
                        {"id": "P00-S01-T001", "title": "A", "phase_id": "P00", "step_id": "P00-S01", "status": state, "depends_on": []},
                        {"id": "P00-S01-T002", "title": "B", "phase_id": "P00", "step_id": "P00-S01", "status": "blocked", "depends_on": ["P00-S01-T001"]},
                    ]
                    registry = {
                        "generated_at": common.now_iso(),
                        "project_prefix": "TEST",
                        "phase_order": ["P00"],
                        "phases": [{"id": "P00", "title": "P0", "status": "blocked", "task_ids": [t["id"] for t in tasks]}],
                        "tasks": tasks,
                        "journeys": [],
                        "task_dag": boot.build_task_dag(tasks),
                    }
                    refreshed = common.refresh_phase_statuses(registry)
                    self.assertEqual(refreshed["phases"][0]["status"], "active", state)
        finally:
            td.cleanup()

    def test_claim_denies_join_until_all_predecessors_done(self):
        root, td = _setup_root()
        try:
            with _Sandbox(root):
                import common
                import claim_task
                tasks = [
                    {"id": "P00-S01-T001", "title": "A", "phase_id": "P00", "step_id": "P00-S01", "status": "done", "depends_on": []},
                    {"id": "P00-S01-T002", "title": "B", "phase_id": "P00", "step_id": "P00-S01", "status": "ready", "depends_on": []},
                    {"id": "P00-S02-T001", "title": "Join", "phase_id": "P00", "step_id": "P00-S02", "status": "blocked", "depends_on": ["P00-S01-T001", "P00-S01-T002"]},
                ]
                common.save_registry({
                    "generated_at": common.now_iso(),
                    "project_prefix": "TEST",
                    "phase_order": ["P00"],
                    "phases": [{"id": "P00", "title": "P0", "status": "active", "task_ids": [t["id"] for t in tasks]}],
                    "tasks": tasks,
                    "journeys": [],
                    "task_dag": boot.build_task_dag(tasks),
                })
                common.save_runtime_state({
                    "generated_at": common.now_iso(),
                    "last_worker": None,
                    "last_event": None,
                    "pending_journey_verifications": [],
                    "last_journey_verified": None,
                    "spawn_budget": 20,
                    "spawns_in_current_slice": {},
                })
                ok, result = claim_task.claim_task("P00-S02-T001")
                self.assertFalse(ok)
                self.assertEqual(result["missing_dependencies"], ["P00-S01-T002"])

                registry = common.load_registry()
                for t in registry["tasks"]:
                    if t["id"] == "P00-S01-T002":
                        t["status"] = "done"
                common.save_registry(common.promote_ready_tasks(registry))
                ok, result = claim_task.claim_task("P00-S02-T001")
                self.assertTrue(ok)
                self.assertEqual(result["task"]["status"], "claimed")
        finally:
            td.cleanup()

    def test_post_tool_ledger_uses_per_terminal_env_override(self):
        root, td = _setup_root()
        try:
            with _Sandbox(root):
                import common
                import hook_update_ledger
                self._seed_registry(common)
                os.environ["CLAUDE_ACTIVE_TASK_ID"] = "P00-S01-T002"
                payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": "lib/b.dart"}})
                with mock.patch.object(sys, "stdin", StringIO(payload)):
                    hook_update_ledger.main()
                lines = (root / "orchestrator-state" / "tasks" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
                record = json.loads(lines[-1])
                self.assertEqual(record["task_id"], "P00-S01-T002")
                self.assertEqual(record["phase_id"], "P00")
                self.assertEqual(record["file_path"], "lib/b.dart")
        finally:
            td.cleanup()

    def test_post_tool_ledger_routes_git_close_housekeeping_bash_to_runtime_ledger(self):
        root, td = _setup_root()
        try:
            with _Sandbox(root):
                import common
                import hook_update_ledger
                self._seed_registry(common)
                ledger = root / "orchestrator-state" / "tasks" / "ledger.jsonl"
                bash_ledger = root / "orchestrator-state" / "tasks" / "bash-ledger.jsonl"
                commands = [
                    "git status --short",
                    "git add -A && git commit -m close",
                    "./scripts/git-workflow.sh",
                    "bash scripts/slice-clean.sh --apply",
                    "bash scripts/cleanup-worktrees.sh --apply --task P00-S01-T001 --schedule-active",
                ]
                for command in commands:
                    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
                    with mock.patch.object(sys, "stdin", StringIO(payload)):
                        hook_update_ledger.main()
                self.assertFalse(ledger.exists(), "Bash commands must not append the canonical ledger after close commit")
                self.assertTrue(bash_ledger.exists(), "Bash commands remain traceable in runtime-only bash-ledger.jsonl")
        finally:
            td.cleanup()

    def test_post_tool_ledger_keeps_product_bash_traceability(self):
        root, td = _setup_root()
        try:
            with _Sandbox(root):
                import common
                import hook_update_ledger
                self._seed_registry(common)
                command = "pytest backend/tests -k health"
                payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
                with mock.patch.object(sys, "stdin", StringIO(payload)):
                    hook_update_ledger.main()
                lines = (root / "orchestrator-state" / "tasks" / "bash-ledger.jsonl").read_text(encoding="utf-8").splitlines()
                record = json.loads(lines[-1])
                self.assertEqual(record["tool_name"], "Bash")
                self.assertEqual(record["command"], command)
        finally:
            td.cleanup()

    def test_async_tests_use_per_terminal_env_override_commands_and_evidence(self):
        root, td = _setup_root()
        try:
            with _Sandbox(root):
                import common
                import run_tests_async
                self._seed_registry(common)
                registry = common.load_registry()
                for task in registry["tasks"]:
                    if task["id"] == "P00-S01-T001":
                        task["verification_commands"] = ["python3 -c 'print(\"wrong\")'"]
                    if task["id"] == "P00-S01-T002":
                        task["verification_commands"] = ["python3 -c 'print(\"right\")'"]
                common.save_registry(registry)
                os.environ["CLAUDE_ACTIVE_TASK_ID"] = "P00-S01-T002"
                payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": "lib/b.dart"}})
                with mock.patch.object(sys, "stdin", StringIO(payload)):
                    run_tests_async.main()
                log = root / "orchestrator-state" / "tasks" / "evidence" / "P00-S01-T002" / "async-check.log"
                self.assertTrue(log.exists())
                body = log.read_text(encoding="utf-8")
                self.assertIn("right", body)
                self.assertNotIn("wrong", body)
        finally:
            td.cleanup()

    def test_subagent_stop_scope_mismatch_does_not_mutate_wrong_task(self):
        root, td = _setup_root()
        try:
            with _Sandbox(root):
                import common
                import hook_capture_subagent_stop
                self._seed_registry(common)
                os.environ["CLAUDE_ACTIVE_TASK_ID"] = "P00-S01-T002"
                payload = json.dumps({
                    "agent_type": "developer",
                    "last_assistant_message": (
                        "CLAUDE_TRAILER:\n"
                        "TASK_ID: P00-S01-T001\n"
                        "OUTCOME: pass\n"
                        "NEXT_STATUS: review_pending\n"
                    ),
                })
                with mock.patch.object(sys, "stdin", StringIO(payload)):
                    hook_capture_subagent_stop.main()
                by_id = {t["id"]: t for t in common.load_registry()["tasks"]}
                self.assertEqual(by_id["P00-S01-T001"]["status"], "ready")
                self.assertEqual(by_id["P00-S01-T002"]["status"], "ready")
                self.assertEqual(common.get_spawn_count("P00-S01-T002"), 1)
                err_log = root / "orchestrator-state" / "hook-errors.log"
                self.assertTrue(err_log.exists())
                self.assertIn("TASK_ID mismatch", err_log.read_text(encoding="utf-8"))
        finally:
            td.cleanup()

    def test_spawn_budget_uses_per_terminal_env_override(self):
        root, td = _setup_root()
        try:
            with _Sandbox(root):
                import common
                import hook_spawn_budget
                self._seed_registry(common)
                for i in range(20):
                    common.bump_spawn_count("P00-S01-T002", f"agent_{i}")
                os.environ["CLAUDE_ACTIVE_TASK_ID"] = "P00-S01-T002"
                payload = json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": "developer"}})
                out = StringIO()
                with mock.patch.object(sys, "stdin", StringIO(payload)), mock.patch.object(sys, "stdout", out):
                    hook_spawn_budget.main()
                body = out.getvalue()
                self.assertIn("permissionDecision", body)
                self.assertIn("P00-S01-T002", body)
        finally:
            td.cleanup()


class HookUpdateLedgerGitCloseTests(unittest.TestCase):
    def test_bash_events_use_ignored_runtime_ledger(self):
        import hook_update_ledger
        self.assertEqual(hook_update_ledger._ledger_for_tool("Bash").name, "bash-ledger.jsonl")
        self.assertEqual(hook_update_ledger._ledger_for_tool("Write").name, "ledger.jsonl")
        self.assertEqual(hook_update_ledger._ledger_for_tool("Edit").name, "ledger.jsonl")


if __name__ == "__main__":
    unittest.main(verbosity=2)

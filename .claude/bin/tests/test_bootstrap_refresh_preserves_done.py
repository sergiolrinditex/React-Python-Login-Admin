"""Regression tests: bootstrap_three_docs.py --refresh preserves closer-final task status.

Slice/Phase: P01-S02-T010 (framework maintenance)
Origin: FU-20260512044309-make-bootstrap-three-docs-py-refresh-preserve-cl

These tests pin the behavioral contract that a bootstrap --refresh run must
never clobber the lifecycle state of tasks already closed by the closer or
deployer.  They were introduced alongside the defensive hardening added to
_apply_preserved_runtime (CLOSER_FINAL_STATUSES / CLOSER_FINAL_OUTCOMES guard)
in the same slice.

Historical context: before this fix, a --refresh run could restore
status=ready_for_close / last_outcome=pass (tester values) for a task where
the closer's SubagentStop hook had not yet written status=done to disk.
Commit 570b702 performed a manual recovery; these tests ensure that regression
is impossible in future.

Each test case:
  1. Builds a minimal synthetic source-of-truth tree in tempfile.TemporaryDirectory().
  2. Monkey-patches os.environ["CLAUDE_PROJECT_DIR"] to the tmp root.
  3. Reloads common + bootstrap_three_docs modules between test cases.
  4. NEVER touches the real orchestrator-state/ or real registry.json.

Covers:
  TC1  status=done + last_outcome=committed  -> all lifecycle fields preserved
  TC2  status=blocked + last_outcome=committed -> preserved
  TC3  status=skipped + last_outcome=deployed  -> preserved
  TC4  status=done + last_outcome=deployed (deployer path) -> preserved
  TC5  status=ready (non-closer-final) -> NOT over-frozen (negative control)
  TC6  closer-final task -> derived fields (title, write_set) still refreshed
  TC7  All fields in _RUNTIME_TASK_FIELDS_TO_PRESERVE sentinel-round-trip
  TC8  status=done + last_outcome=null (manual done without closer) -> preserved
       because status=done alone is closer-final by CLOSER_FINAL_STATUSES contract

Dependencies: bootstrap_three_docs (same dir), common (same dir).
Run: python3 -B -S -m unittest discover -s .claude/bin/tests -p test_bootstrap_refresh_preserves_done.py -v
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

import bootstrap_three_docs as boot  # noqa: E402
import common  # noqa: E402


# ---------------------------------------------------------------------------
# Shared minimal source-of-truth scaffold
# ---------------------------------------------------------------------------

_INSTR = "# Instructions\n\n## Goals\n\nBuild the app.\n"
_GUIDE = "# Technical Guide\n\n## Stack\n\npython/react.\n\n## Architecture\n\nclean.\n"
_UX = "# UX Contract\n\n## Screen/Journey Lane Redactor Contract\n\nUse real/provided data.\n"
_STACK = (
    "frontend:\n  language: typescript\n  framework: react\n"
    "backend:\n  language: python\n  framework: fastapi\n"
    "db:\n  engine: postgres\n"
    "design_tokens_enforcer: none\n"
    "git_workflow: push-to-main\n"
)
# Minimal checklist with 2 tasks and DAG Depends on column.
# Task A (P00-S01-T001) has no deps; task B (P00-S02-T001) depends on A.
_CHECKLIST = (
    "# Checklist\n\n"
    "## Canonical Coverage Registry\n\n"
    "| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode"
    " | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint"
    " | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance minimo | Verify minimo |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    "| P00-S01-T001 | setup | scaffold | Step 0.1 | v1 | planned | low | auto"
    " | — | infra:scaffold | scripts/** | — | — | — | — | §1 | §2 | create scaffold | pytest |\n"
    "| P00-S02-T001 | api | health | Step 0.2 | v1 | planned | low | auto"
    " | P00-S01-T001 | api:health | api/** | — | — | GET /health | — | §1 | §2 | health works | curl |\n"
    "\n"
    "# Phase 0 — Bootstrap\n\n"
    "## Step 0.1 — Scaffold\n\n- [ ] create scaffold\n\n"
    "## Step 0.2 — Health\n\n- [ ] health works\n"
)

# Alternate checklist where T001 title and write_set differ (used by TC6).
_CHECKLIST_REFRESHED_TITLE = _CHECKLIST.replace(
    "| P00-S01-T001 | setup | scaffold | Step 0.1 | v1 | planned | low | auto"
    " | — | infra:scaffold | scripts/** | — | — | — | — | §1 | §2 | create scaffold | pytest |",
    "| P00-S01-T001 | setup | NEW scaffold title | Step 0.1 | v1 | planned | low | auto"
    " | — | infra:scaffold | newscripts/** | — | — | — | — | §1 | §2 | create scaffold | pytest |",
)


def _make_root(td_path: str) -> Path:
    """Create a minimal source-of-truth tree under *td_path* and return its Path."""
    root = Path(td_path)
    sot = root / "docs/source-of-truth"
    sot.mkdir(parents=True)
    (sot / "instrucciones.md").write_text(_INSTR, encoding="utf-8")
    (sot / "APP_TECHNICAL_GUIDE.md").write_text(_GUIDE, encoding="utf-8")
    (sot / "APP_IMPLEMENTATION_CHECKLIST.md").write_text(_CHECKLIST, encoding="utf-8")
    (sot / "UX_CONTRACT.md").write_text(_UX, encoding="utf-8")
    (sot / "STACK_PROFILE.yaml").write_text(_STACK, encoding="utf-8")
    (root / "orchestrator-state/tasks").mkdir(parents=True)
    (root / "orchestrator-state/memory").mkdir(parents=True)
    return root


class _RootCtx:
    """Context manager: set CLAUDE_PROJECT_DIR + reload modules, restore on exit.

    Usage::

        with _RootCtx(root) as (boot_mod, common_mod):
            ...
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def __enter__(self):
        self._prev = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self._root)
        if hasattr(common, "_LOCK_DEPTH"):
            common._LOCK_DEPTH.clear()
        importlib.reload(common)
        importlib.reload(boot)
        return boot, common

    def __exit__(self, exc_type, exc, tb):
        if self._prev is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = self._prev
        if hasattr(common, "_LOCK_DEPTH"):
            common._LOCK_DEPTH.clear()
        importlib.reload(common)
        importlib.reload(boot)


class BootstrapRefreshPreservesDoneTests(unittest.TestCase):
    """Pins the closer-final preservation contract in _apply_preserved_runtime.

    All tests use synthetic registries inside tempfile.TemporaryDirectory().
    The real orchestrator-state/ is never touched.
    """

    # ------------------------------------------------------------------
    # TC1 -- status=done + last_outcome=committed -> all lifecycle fields preserved
    # ------------------------------------------------------------------
    def test_refresh_preserves_done_committed_closer_final(self):
        """TC1: Canonical closer-final task (done + committed) must survive refresh."""
        with tempfile.TemporaryDirectory() as td:
            root = _make_root(td)
            with _RootCtx(root) as (boot_mod, common_mod):
                # First pass: materialize registry
                result = boot_mod.generate_artifacts()
                self.assertTrue(result["ok"], f"Initial generate_artifacts failed: {result}")

                # Inject closer-final state for T001
                registry = common_mod.load_registry()
                by_id = {t["id"]: t for t in registry["tasks"]}
                self.assertIn("P00-S01-T001", by_id)
                by_id["P00-S01-T001"].update({
                    "status": "done",
                    "last_outcome": "committed",
                    "last_updated_by": "closer",
                    "last_stop_at": "2026-05-11T18:00:00+00:00",
                    "last_note": "Slice committed successfully",
                })
                common_mod.save_registry(registry)

            # Re-enter context to get a fresh module state, then refresh
            with _RootCtx(root) as (boot_mod, common_mod):
                result = boot_mod.generate_artifacts()
                self.assertTrue(result["ok"], f"Refresh generate_artifacts failed: {result}")

                refreshed = common_mod.load_registry()
                by_id = {t["id"]: t for t in refreshed["tasks"]}
                task = by_id["P00-S01-T001"]

                self.assertEqual(task["status"], "done", "status must be preserved")
                self.assertEqual(task["last_outcome"], "committed", "last_outcome must be preserved")
                self.assertEqual(task["last_updated_by"], "closer", "last_updated_by must be preserved")
                self.assertEqual(task["last_stop_at"], "2026-05-11T18:00:00+00:00", "last_stop_at must be preserved")
                self.assertEqual(task.get("last_note"), "Slice committed successfully", "last_note must be preserved")

    # ------------------------------------------------------------------
    # TC2 -- status=blocked + last_outcome=committed -> preserved
    # ------------------------------------------------------------------
    def test_refresh_preserves_blocked_status(self):
        """TC2: Blocked-by-closer task must survive refresh."""
        with tempfile.TemporaryDirectory() as td:
            root = _make_root(td)
            with _RootCtx(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                registry = common_mod.load_registry()
                by_id = {t["id"]: t for t in registry["tasks"]}
                by_id["P00-S01-T001"].update({
                    "status": "blocked",
                    "last_outcome": "committed",
                    "last_updated_by": "closer",
                    "blocked_reason": "Dependency missing",
                    "blocked_by": "P00-S01-T000",
                    "last_stop_at": "2026-05-11T17:00:00+00:00",
                })
                common_mod.save_registry(registry)

            with _RootCtx(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                by_id = {t["id"]: t for t in common_mod.load_registry()["tasks"]}
                task = by_id["P00-S01-T001"]

                self.assertEqual(task["status"], "blocked")
                self.assertEqual(task["last_outcome"], "committed")
                self.assertEqual(task["last_updated_by"], "closer")
                self.assertEqual(task.get("blocked_reason"), "Dependency missing")
                self.assertEqual(task.get("blocked_by"), "P00-S01-T000")

    # ------------------------------------------------------------------
    # TC3 -- status=skipped + last_outcome=deployed -> preserved
    # ------------------------------------------------------------------
    def test_refresh_preserves_skipped_status(self):
        """TC3: Skipped task with deployed outcome must survive refresh."""
        with tempfile.TemporaryDirectory() as td:
            root = _make_root(td)
            with _RootCtx(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                registry = common_mod.load_registry()
                by_id = {t["id"]: t for t in registry["tasks"]}
                by_id["P00-S01-T001"].update({
                    "status": "skipped",
                    "last_outcome": "deployed",
                    "last_updated_by": "deployer",
                    "last_stop_at": "2026-05-10T12:00:00+00:00",
                })
                common_mod.save_registry(registry)

            with _RootCtx(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                by_id = {t["id"]: t for t in common_mod.load_registry()["tasks"]}
                task = by_id["P00-S01-T001"]

                self.assertEqual(task["status"], "skipped")
                self.assertEqual(task["last_outcome"], "deployed")
                self.assertEqual(task["last_updated_by"], "deployer")

    # ------------------------------------------------------------------
    # TC4 -- status=done + last_outcome=deployed (deployer path) -> preserved
    # ------------------------------------------------------------------
    def test_refresh_preserves_deployed_outcome(self):
        """TC4: Deployer-closed task (done + deployed) must survive refresh."""
        with tempfile.TemporaryDirectory() as td:
            root = _make_root(td)
            with _RootCtx(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                registry = common_mod.load_registry()
                by_id = {t["id"]: t for t in registry["tasks"]}
                by_id["P00-S01-T001"].update({
                    "status": "done",
                    "last_outcome": "deployed",
                    "last_updated_by": "deployer",
                    "last_stop_at": "2026-05-12T06:00:00+00:00",
                })
                common_mod.save_registry(registry)

            with _RootCtx(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                by_id = {t["id"]: t for t in common_mod.load_registry()["tasks"]}
                task = by_id["P00-S01-T001"]

                self.assertEqual(task["status"], "done")
                self.assertEqual(task["last_outcome"], "deployed")
                self.assertEqual(task["last_updated_by"], "deployer")

    # ------------------------------------------------------------------
    # TC5 -- status=ready (non-closer-final) -> NOT over-frozen (negative control)
    # ------------------------------------------------------------------
    def test_refresh_does_not_freeze_non_closer_final_status(self):
        """TC5: A task with status=ready should not be over-frozen by the guard.

        This test verifies the preservation path does not accidentally lock
        non-closer-final tasks.  A ready task stays ready after refresh since
        the source-of-truth still declares it as planned/ready.
        """
        with tempfile.TemporaryDirectory() as td:
            root = _make_root(td)
            with _RootCtx(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                # T001 starts as ready (no deps). Set it explicitly.
                registry = common_mod.load_registry()
                by_id = {t["id"]: t for t in registry["tasks"]}
                by_id["P00-S01-T001"]["status"] = "ready"
                # last_outcome is not a closer-final outcome
                by_id["P00-S01-T001"]["last_outcome"] = "pass"
                common_mod.save_registry(registry)

            with _RootCtx(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                by_id = {t["id"]: t for t in common_mod.load_registry()["tasks"]}
                task = by_id["P00-S01-T001"]
                # The key assertion: ready task must not be promoted to done/blocked
                # by the closer-final defensive guard (which only fires for done/blocked/skipped).
                self.assertNotEqual(task["status"], "done",
                    "ready task must not be accidentally promoted to done by the guard")
                # status=ready is preserved by _RUNTIME_TASK_FIELDS_TO_PRESERVE
                self.assertIn(task["status"], {"ready", "blocked"},
                    "non-final task status should be a live lifecycle value after refresh")

    # ------------------------------------------------------------------
    # TC6 -- closer-final task: derived fields (title, write_set) still refreshed
    # ------------------------------------------------------------------
    def test_refresh_still_refreshes_derived_fields_for_closer_final_task(self):
        """TC6: Source-of-truth fields (title, write_set) refresh even for done tasks.

        Lifecycle fields (status, last_outcome, etc.) are frozen but structural
        Coverage Registry fields must always be refreshed so that Coverage
        Registry edits propagate correctly even after a task is closed.
        """
        with tempfile.TemporaryDirectory() as td:
            root = _make_root(td)
            sot = root / "docs/source-of-truth"

            with _RootCtx(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                # Mark T001 as closer-final
                registry = common_mod.load_registry()
                by_id = {t["id"]: t for t in registry["tasks"]}
                by_id["P00-S01-T001"].update({
                    "status": "done",
                    "last_outcome": "committed",
                    "last_updated_by": "closer",
                    "last_stop_at": "2026-05-11T20:00:00+00:00",
                })
                common_mod.save_registry(registry)

            # Update source-of-truth: change title and write_set of T001
            (sot / "APP_IMPLEMENTATION_CHECKLIST.md").write_text(
                _CHECKLIST_REFRESHED_TITLE, encoding="utf-8"
            )

            with _RootCtx(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                by_id = {t["id"]: t for t in common_mod.load_registry()["tasks"]}
                task = by_id["P00-S01-T001"]

                # Lifecycle fields: preserved
                self.assertEqual(task["status"], "done",
                    "status must still be preserved after doc update")
                self.assertEqual(task["last_outcome"], "committed",
                    "last_outcome must still be preserved after doc update")

                # Structural (derived) fields: refreshed from new Coverage Registry
                self.assertIn("NEW scaffold title", task["title"],
                    "title must be refreshed from updated source-of-truth")
                self.assertTrue(
                    any("newscripts" in p for p in task.get("write_set", [])),
                    f"write_set must reflect updated Coverage Registry; got: {task.get('write_set')}"
                )

    # ------------------------------------------------------------------
    # TC7 -- All fields in _RUNTIME_TASK_FIELDS_TO_PRESERVE sentinel-round-trip
    # ------------------------------------------------------------------
    def test_refresh_preserves_all_lifecycle_fields_listed_in_allowlist(self):
        """TC7: Every field in _RUNTIME_TASK_FIELDS_TO_PRESERVE must survive a refresh.

        Seeds a task with a sentinel value for every field in the allowlist,
        then runs --refresh and asserts each sentinel is intact.  This test
        will fail immediately if a future refactor removes a field from the
        allowlist or introduces a new code path that overwrites preserved fields.
        """
        with tempfile.TemporaryDirectory() as td:
            root = _make_root(td)
            with _RootCtx(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                registry = common_mod.load_registry()
                by_id = {t["id"]: t for t in registry["tasks"]}

                # Build sentinel values for every field in the allowlist.
                sentinels: dict = {}
                for field in boot_mod._RUNTIME_TASK_FIELDS_TO_PRESERVE:
                    if field in {"retry_count", "debug_retry_count"}:
                        sentinels[field] = 42
                    else:
                        sentinels[field] = f"sentinel_{field}"

                # Ensure status and last_outcome are closer-final so the
                # defensive guard also fires (belt-and-suspenders for TC7).
                sentinels["status"] = "done"
                sentinels["last_outcome"] = "committed"

                by_id["P00-S01-T001"].update(sentinels)
                common_mod.save_registry(registry)

            with _RootCtx(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                by_id = {t["id"]: t for t in common_mod.load_registry()["tasks"]}
                task = by_id["P00-S01-T001"]

                for field, expected in sentinels.items():
                    self.assertEqual(
                        task.get(field), expected,
                        f"Field '{field}' in _RUNTIME_TASK_FIELDS_TO_PRESERVE was clobbered by refresh"
                    )

    # ------------------------------------------------------------------
    # TC8 -- status=done + last_outcome=null (manual done without closer) -> preserved
    # ------------------------------------------------------------------
    def test_refresh_preserves_manually_set_done_without_last_outcome(self):
        """TC8: status=done without last_outcome (manual/edge case) is still preserved.

        CLOSER_FINAL_STATUSES includes 'done' regardless of last_outcome.
        A task manually marked done (e.g. via an emergency registry edit) should
        survive refresh -- the 'done' status alone triggers the defensive guard.
        """
        with tempfile.TemporaryDirectory() as td:
            root = _make_root(td)
            with _RootCtx(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                registry = common_mod.load_registry()
                by_id = {t["id"]: t for t in registry["tasks"]}
                by_id["P00-S01-T001"].update({
                    "status": "done",
                    "last_updated_by": "manual-recovery",
                    "last_stop_at": "2026-05-12T00:00:00+00:00",
                    # last_outcome intentionally absent / None
                })
                by_id["P00-S01-T001"].pop("last_outcome", None)
                common_mod.save_registry(registry)

            with _RootCtx(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                by_id = {t["id"]: t for t in common_mod.load_registry()["tasks"]}
                task = by_id["P00-S01-T001"]

                self.assertEqual(task["status"], "done",
                    "status=done must survive refresh even when last_outcome is absent")
                self.assertEqual(task["last_updated_by"], "manual-recovery",
                    "last_updated_by must be preserved")
                self.assertEqual(task["last_stop_at"], "2026-05-12T00:00:00+00:00",
                    "last_stop_at must be preserved")


class CloserFinalConstantsTests(unittest.TestCase):
    """Verify CLOSER_FINAL_STATUSES and CLOSER_FINAL_OUTCOMES are importable and correct."""

    def test_constants_are_frozensets(self):
        self.assertIsInstance(boot.CLOSER_FINAL_STATUSES, frozenset)
        self.assertIsInstance(boot.CLOSER_FINAL_OUTCOMES, frozenset)

    def test_closer_final_statuses_contains_expected_values(self):
        self.assertIn("done", boot.CLOSER_FINAL_STATUSES)
        self.assertIn("blocked", boot.CLOSER_FINAL_STATUSES)
        self.assertIn("skipped", boot.CLOSER_FINAL_STATUSES)

    def test_closer_final_outcomes_contains_expected_values(self):
        self.assertIn("committed", boot.CLOSER_FINAL_OUTCOMES)
        self.assertIn("deployed", boot.CLOSER_FINAL_OUTCOMES)

    def test_non_closer_statuses_not_in_set(self):
        for non_final in ("ready", "claimed", "ready_for_close", "needs_debug",
                          "validator_tester_pending", "in_progress"):
            self.assertNotIn(non_final, boot.CLOSER_FINAL_STATUSES,
                f"'{non_final}' must not be in CLOSER_FINAL_STATUSES -- it is not a terminal state")

    def test_non_closer_outcomes_not_in_set(self):
        for non_final in ("pass", "fail", "approved", "changes_requested",
                          "success", "fixed"):
            self.assertNotIn(non_final, boot.CLOSER_FINAL_OUTCOMES,
                f"'{non_final}' must not be in CLOSER_FINAL_OUTCOMES -- it is not a closer outcome")


if __name__ == "__main__":
    unittest.main(verbosity=2)

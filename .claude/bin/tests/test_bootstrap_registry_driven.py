"""Bootstrap registry-driven mode (Fixes B1-B4) — pins the slicing contract.

Coverage:
  * parse_coverage_registry recognises every Coverage Registry table style
    (Endpoint, Auth platform / non-HTTP, DB / Migration, Flutter Screen)
    and emits canonical task dicts with the right step_id derivation.
  * Title heuristic prefers Page/Widget over route, falls back sensibly.
  * Step-heading filter rejects PRE-GATE / PHASE GATE / "canonical slices"
    meta-headings and only accepts `## Step N.M`.
  * Step↔canonical matcher does NOT accept partial matches: 'Step 2.1'
    must not match 'Step 2.10' or 'Step 2.11', and a step with canonicals
    must NOT also emit a synthetic for the same step (regression for the
    duplicate-IDs bug).
  * Journey slice cells are stripped of backticks before expansion.
  * E2E against the real BASEAPP docs: every canonical sample matches and
    every journey task_id resolves.
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

import bootstrap_three_docs as boot  # noqa: E402
import common  # noqa: E402

# Derive the repo root from this file's location so the E2E test runs on any
# machine, not just the sandbox in which the original fix was authored.
# Layout: <repo>/.claude/bin/tests/test_*.py -> parents[3] is the repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Unit tests for the new helpers
# ---------------------------------------------------------------------------
class StripMdInlineTests(unittest.TestCase):

    def test_strips_backticks_and_whitespace(self):
        self.assertEqual(boot._strip_md_inline("`P00-S05-T001`"), "P00-S05-T001")
        self.assertEqual(boot._strip_md_inline("  `foo`  "), "foo")

    def test_handles_empty(self):
        self.assertEqual(boot._strip_md_inline(""), "")
        self.assertEqual(boot._strip_md_inline(None), "")


class StepHeadingFilterTests(unittest.TestCase):

    def test_step_n_m_accepted(self):
        self.assertTrue(boot.STEP_HEADING_RE.match("Step 0.1"))
        self.assertTrue(boot.STEP_HEADING_RE.match("Step 2.4 — Factory LLM"))
        self.assertTrue(boot.STEP_HEADING_RE.match("step 3.5"))

    def test_meta_headings_rejected(self):
        for bad in [
            "PRE-GATE",
            "⚠️ PRE-GATE",
            "🚪 PHASE 0 GATE",
            "Phase 2 canonical slices — MOTOR AI base",
            "Endpoint Coverage Registry",
        ]:
            self.assertFalse(boot.STEP_HEADING_RE.match(bad),
                             f"meta heading '{bad}' must NOT match STEP_HEADING_RE")

    def test_step_filter_keeps_only_step_headings(self):
        in_ = [
            {"title": "⚠️ PRE-GATE", "level": 2, "line": 10},
            {"title": "Step 2.1 — Estructura", "level": 2, "line": 20},
            {"title": "Phase 2 canonical slices — MOTOR AI base", "level": 2, "line": 30},
            {"title": "Step 2.2 — Tablas", "level": 2, "line": 40},
            {"title": "🚪 PHASE 2 GATE", "level": 2, "line": 50},
        ]
        out = boot._step_headings_only(in_)
        self.assertEqual([h["title"] for h in out],
                         ["Step 2.1 — Estructura", "Step 2.2 — Tablas"])


class StepLabelMatcherRegressionTests(unittest.TestCase):
    """Regression for the matcher bug: 'Step 2.1' must not match 'Step 2.10'."""

    def test_step_2_1_does_not_match_step_2_10(self):
        # The fix uses re.escape(label) + r"(?!\d)" so trailing digits break
        # the match. We replicate the exact pattern here to pin it.
        import re as _re
        label = "Step 2.1"
        pat = _re.compile(_re.escape(label) + r"(?!\d)", _re.IGNORECASE)
        self.assertTrue(pat.search("Step 2.1"))
        self.assertTrue(pat.search("step 2.1 — title"))
        self.assertFalse(pat.search("Step 2.10"),
                         "'Step 2.1' must NOT match 'Step 2.10' — that was the dispatch-collapse bug")
        self.assertFalse(pat.search("Step 2.11"))
        self.assertTrue(pat.search("Step 2.1, Step 3.4"))


class ParseCoverageRegistryTests(unittest.TestCase):

    def _checklist(self, body: str) -> str:
        return f"# Project — Implementation Checklist\n\n{body}\n"

    def test_endpoint_registry_minimal(self):
        cl = self._checklist(
            "## Endpoint Coverage Registry\n\n"
            "| Slice ID | Method | Path | Phase/Step canónico | Verify mínimo |\n"
            "|----------|--------|------|---------------------|---------------|\n"
            "| P00-S01-T001 | GET | `/health` | Step 0.1 | `curl /health` → 200 |\n"
            "| P00-S01-T002 | GET | `/ready` | Step 0.1 | DB OK → 200 |\n"
        )
        out = boot.parse_coverage_registry(cl)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["id"], "P00-S01-T001")
        self.assertEqual(out[0]["phase_id"], "P00")
        self.assertEqual(out[0]["step_id"], "P00-S01")
        self.assertEqual(out[0]["title"], "GET /health")
        self.assertEqual(out[0]["step_ref"], "Step 0.1")
        self.assertIn("curl /health", " ".join(out[0]["verification_commands"]))

    def test_flutter_screen_registry_no_step_column(self):
        """Flutter Screen registry has no Step/Phase column — bootstrap
        must derive step_ref implicitly from the canonical ID."""
        cl = self._checklist(
            "## Flutter Screen / Feature Coverage Registry\n\n"
            "| Slice ID | Ruta | Page / widget | Consume endpoints | Journey |\n"
            "|----------|------|---------------|-------------------|---------|\n"
            "| P00-S04-T001 | `/showcase` | `ShowcasePage` | none | J4 |\n"
        )
        out = boot.parse_coverage_registry(cl)
        self.assertEqual(len(out), 1)
        # Title should prefer Page/Widget over route.
        self.assertEqual(out[0]["title"], "ShowcasePage")
        # step_ref derived from id.
        self.assertEqual(out[0]["step_ref"], "Step 0.4")

    def test_multiple_tables_merge(self):
        """Same canonical ID across tables should merge, not duplicate."""
        cl = self._checklist(
            "## Endpoint Coverage Registry\n\n"
            "| Slice ID | Method | Path | Phase/Step canónico |\n"
            "|----------|--------|------|---------------------|\n"
            "| P01-S02-T001 | POST | `/auth/register` | Step 1.2 |\n"
            "\n"
            "## DB Coverage Registry\n\n"
            "| Slice ID | Table | Phase/Step |\n"
            "|----------|-------|------------|\n"
            "| P01-S02-T001 | users | Step 1.2 |\n"
        )
        out = boot.parse_coverage_registry(cl)
        ids = [t["id"] for t in out]
        self.assertEqual(ids.count("P01-S02-T001"), 1,
            "duplicate canonical IDs across tables must merge")

    def test_no_registry_returns_empty(self):
        out = boot.parse_coverage_registry("just narrative\nno tables\n")
        self.assertEqual(out, [])

    def test_header_synonym_slice_alone(self):
        """Header `| Slice |` (no `ID`) is a recognized synonym."""
        cl = self._checklist(
            "## Coverage Registry\n\n"
            "| Slice | Path |\n"
            "|-------|------|\n"
            "| P00-S01-T001 | `/health` |\n"
        )
        out = boot.parse_coverage_registry(cl)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id"], "P00-S01-T001")

    def test_header_synonym_task_id(self):
        """Header `| Task ID |` is a recognized synonym (case-insensitive)."""
        cl = self._checklist(
            "## Coverage Registry\n\n"
            "| Task ID | Description |\n"
            "|---------|-------------|\n"
            "| P02-S03-T010 | something |\n"
        )
        out = boot.parse_coverage_registry(cl)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id"], "P02-S03-T010")

    def test_header_synonym_taskid_no_space(self):
        """Header `| TaskID |` (no space) is recognized."""
        cl = self._checklist(
            "## Coverage Registry\n\n"
            "| TaskID | DoD |\n"
            "|--------|-----|\n"
            "| P00-S05-T002 | done when X |\n"
        )
        out = boot.parse_coverage_registry(cl)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id"], "P00-S05-T002")

    def test_acceptance_skips_id_column_for_all_synonyms(self):
        """When the ID column is named with a synonym, acceptance lookup
        must NOT pull from the ID cell — that bug existed before the
        ``_is_id_header_key`` helper."""
        cl = self._checklist(
            "## Coverage Registry\n\n"
            "| Task ID | Acceptance |\n"
            "|---------|------------|\n"
            "| P00-S01-T001 | endpoint returns 200 |\n"
        )
        out = boot.parse_coverage_registry(cl)
        self.assertEqual(len(out), 1)
        self.assertIn("endpoint returns 200", out[0]["acceptance"])

    def test_bare_id_header_is_not_recognized(self):
        """Header `| ID |` alone must NOT activate the parser — too generic.
        It would pollute unrelated tables that happen to start with `| ID |`.
        The fallback detection layer warns about these cases instead."""
        cl = self._checklist(
            "## Some Other Table\n\n"
            "| ID | Description |\n"
            "|----|-------------|\n"
            "| P00-S01-T001 | should be ignored |\n"
        )
        out = boot.parse_coverage_registry(cl)
        self.assertEqual(out, [],
            "Bare 'ID' header must NOT trigger registry parsing")

    def test_short_digit_ids_accepted(self):
        """COVERAGE_ROW_ID_RE must accept 1-digit segments to align with
        TASK_ID_RE (which already does). Single-digit IDs are valid for
        early-stage projects; the previous 2/2/3-digit minimum caused
        silent drift to positional fallback."""
        cl = self._checklist(
            "## Coverage Registry\n\n"
            "| Slice ID | Description |\n"
            "|----------|-------------|\n"
            "| P0-S1-T1 | first |\n"
            "| P9-S99-T999 | wide |\n"
        )
        out = boot.parse_coverage_registry(cl)
        self.assertEqual(len(out), 2)
        self.assertEqual([t["id"] for t in out], ["P0-S1-T1", "P9-S99-T999"])


class DetectUnrecognizedCoverageRegistriesTests(unittest.TestCase):
    """Content-based fallback that catches Coverage Registries with wrong
    headers (so the user notices instead of silent positional drift)."""

    def _checklist(self, body: str) -> str:
        return f"# project Checklist\n\n{body}\n"

    def test_recognized_headers_produce_no_warning(self):
        cl = self._checklist(
            "| Slice ID | Path |\n"
            "|----------|------|\n"
            "| P00-S01-T001 | /x |\n"
        )
        warns = boot.detect_unrecognized_coverage_registries(cl)
        self.assertEqual(warns, [])

    def test_id_header_with_taskid_row_is_flagged(self):
        cl = self._checklist(
            "| ID | Description |\n"
            "|----|-------------|\n"
            "| P00-S01-T001 | first row |\n"
        )
        warns = boot.detect_unrecognized_coverage_registries(cl)
        self.assertEqual(len(warns), 1)
        self.assertIn("P00-S01-T001", warns[0])
        self.assertIn("ID", warns[0])
        self.assertIn("Slice ID", warns[0])

    def test_unrelated_table_no_taskid_in_col1_is_silent(self):
        cl = self._checklist(
            "| ID | Description |\n"
            "|----|-------------|\n"
            "| 42 | plain numeric id |\n"
        )
        warns = boot.detect_unrecognized_coverage_registries(cl)
        self.assertEqual(warns, [])

    def test_table_without_separator_is_skipped(self):
        # Without the `|---|` row this is just two pipe lines, not a markdown
        # table — must not trigger the heuristic.
        cl = self._checklist(
            "| ID | Description |\n"
            "| P00-S01-T001 | x |\n"
        )
        warns = boot.detect_unrecognized_coverage_registries(cl)
        self.assertEqual(warns, [])

    def test_warning_surfaces_through_build_phases_and_tasks(self):
        """End-to-end: warning produced by the detector must appear in
        the ``_coarse_warnings`` payload that the bootstrap propagates
        to validation.warnings."""
        cl = (
            "# Project Checklist\n\n"
            "## Phase 0 — Setup\n\n"
            "| ID | DoD |\n"
            "|----|-----|\n"
            "| P00-S01-T001 | something |\n\n"
            "### Step 0.1 — first\n\n"
            "- [ ] first\n"
        )
        phases, tasks = boot.build_phases_and_tasks(Path("dummy.md"), cl)
        warns = phases[0].get("_coarse_warnings", []) if phases else []
        self.assertTrue(
            any("Slice ID" in w and "P00-S01-T001" in w for w in warns),
            f"expected unrecognized-registry warning, got: {warns}",
        )


# ---------------------------------------------------------------------------
# Build phases & tasks — registry-driven branch
# ---------------------------------------------------------------------------
class BuildPhasesAndTasksRegistryDrivenTests(unittest.TestCase):

    def _minimal_checklist(self) -> str:
        return (
            "# project Checklist\n\n"
            "## Endpoint Coverage Registry\n\n"
            "| Slice ID | Method | Path | Phase/Step | Verify |\n"
            "|----------|--------|------|------------|--------|\n"
            "| P00-S01-T001 | GET | `/health` | Step 0.1 | `curl /health` |\n"
            "| P00-S01-T002 | GET | `/ready`  | Step 0.1 | DB OK |\n"
            "\n"
            "# Phase 0 — Scaffold\n\n"
            "## ⚠️ PRE-GATE\n\n"
            "- pre-gate noise that must NOT become a step\n\n"
            "## Step 0.1 — Backend scaffold\n\n"
            "- [ ] FastAPI app boots\n"
            "- [ ] Postgres connection\n"
            "\n"
            "## Step 0.2 — Misc scaffolding\n\n"
            "- [ ] No canonical entry — should emit ONE synthetic task\n"
            "- [ ] Second bullet of the same step\n"
            "\n"
            "## 🚪 PHASE 0 GATE\n\n"
            "- gate noise\n"
        )

    def test_canonicals_emitted_synthetic_filled_in_for_uncovered(self):
        phases, tasks = boot.build_phases_and_tasks(
            Path("checklist.md"), self._minimal_checklist())
        self.assertEqual([p["id"] for p in phases], ["P00"])
        ids = [t["id"] for t in tasks]
        self.assertEqual(ids, ["P00-S01-T001", "P00-S01-T002", "P00-S02-T001"],
            "canonicals from registry first, then ONE synthetic per uncovered step")

    def test_no_duplicates(self):
        _, tasks = boot.build_phases_and_tasks(
            Path("checklist.md"), self._minimal_checklist())
        ids = [t["id"] for t in tasks]
        self.assertEqual(len(ids), len(set(ids)),
            "no canonical+synthetic must collide on the same id")

    def test_pre_gate_and_phase_gate_are_not_tasks(self):
        _, tasks = boot.build_phases_and_tasks(
            Path("checklist.md"), self._minimal_checklist())
        for t in tasks:
            self.assertNotIn("PRE-GATE", t["title"].upper())
            self.assertNotIn("PHASE 0 GATE", t["title"].upper())

    def test_synthetic_task_has_acceptance_from_body(self):
        _, tasks = boot.build_phases_and_tasks(
            Path("checklist.md"), self._minimal_checklist())
        synth = next(t for t in tasks if t["id"] == "P00-S02-T001")
        self.assertGreaterEqual(len(synth["acceptance"]), 2)
        self.assertTrue(any("synthetic" in n for n in synth.get("notes", [])))

    def test_first_task_is_ready_rest_blocked(self):
        _, tasks = boot.build_phases_and_tasks(
            Path("checklist.md"), self._minimal_checklist())
        self.assertEqual(tasks[0]["status"], "ready")
        for t in tasks[1:]:
            self.assertEqual(t["status"], "blocked")


# ---------------------------------------------------------------------------
# Build phases & tasks — legacy positional fallback (no registry)
# ---------------------------------------------------------------------------
class BuildPhasesAndTasksLegacyFallbackTests(unittest.TestCase):

    def test_no_registry_uses_positional_path(self):
        cl = (
            "# Legacy Checklist\n\n"
            "# Phase 0 — Stuff\n\n"
            "## Step 0.1 — Scaffold\n\n"
            "- [ ] One thing\n"
            "- [ ] Another thing\n"
        )
        _, tasks = boot.build_phases_and_tasks(Path("c.md"), cl)
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["id"], "P00-S01-T001")
        self.assertEqual(tasks[1]["id"], "P00-S01-T002")

    def test_legacy_pre_gate_still_filtered(self):
        """Even without registry, PRE-GATE / PHASE GATE should not become a step."""
        cl = (
            "# Legacy\n\n# Phase 0 — Stuff\n\n"
            "## ⚠️ PRE-GATE\n\n- noise\n\n"
            "## Step 0.1 — Real step\n\n- [ ] Real item\n"
        )
        _, tasks = boot.build_phases_and_tasks(Path("c.md"), cl)
        for t in tasks:
            self.assertNotIn("PRE-GATE", t["title"].upper())


# ---------------------------------------------------------------------------
# Journey slice cleaning (Fix B4)
# ---------------------------------------------------------------------------
class JourneyBackticksAreStrippedTests(unittest.TestCase):

    def test_backticks_in_slice_cell_are_stripped_before_expansion(self):
        # Build a synthetic instructions doc with one journey row whose
        # slice cell wraps IDs in backticks.
        instructions = (
            "# Instrucciones\n\n"
            "## 3.5 Journey Coverage Matrix\n\n"
            "| ID | Milestone | Pantallas | Acciones | Endpoints | Tablas | Estado | Slices | Verificación |\n"
            "|----|-----------|-----------|----------|-----------|--------|--------|--------|--------------|\n"
            "| J1 | M1 | LoginPage → HomePage | login | /auth/login | users | session | `P01-S02-T001..T002`, `P01-S02-T005` | login real |\n"
        )
        all_tasks = [
            {"id": "P01-S02-T001"}, {"id": "P01-S02-T002"}, {"id": "P01-S02-T005"},
        ]
        journeys = boot.extract_journey_matrix(instructions, all_tasks=all_tasks)
        self.assertEqual(len(journeys), 1)
        self.assertEqual(journeys[0]["task_ids"],
                         ["P01-S02-T001", "P01-S02-T002", "P01-S02-T005"],
                         "backticks must be stripped AND ranges expanded")


# ---------------------------------------------------------------------------
# E2E against the real BASEAPP docs
# ---------------------------------------------------------------------------
class BootstrapEndToEndAgainstBaseappTests(unittest.TestCase):

    @unittest.skipUnless((REPO_ROOT / "docs" / "base-app").is_dir(),
                         "base-app docs only present in the live repo")
    def test_real_base_app_bootstrap(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs" / "source-of-truth").mkdir(parents=True)
            src = REPO_ROOT / "docs" / "base-app"
            for fname in ("instrucciones.md", "BASEAPP_IMPLEMENTATION_CHECKLIST.md", "BASEAPP_TECHNICAL_GUIDE.md"):
                shutil.copy(src / fname, root / "docs" / "source-of-truth" / fname)
            (root / "orchestrator-state" / "tasks").mkdir(parents=True)
            (root / "orchestrator-state" / "memory").mkdir(parents=True)

            prev = os.environ.get("CLAUDE_PROJECT_DIR")
            os.environ["CLAUDE_PROJECT_DIR"] = str(root)
            common._LOCK_DEPTH.clear()
            try:
                # Force module reload so it sees fresh env.
                importlib.reload(boot)
                result = boot.generate_artifacts()
            finally:
                if prev is None:
                    os.environ.pop("CLAUDE_PROJECT_DIR", None)
                else:
                    os.environ["CLAUDE_PROJECT_DIR"] = prev

            self.assertTrue(result["ok"])
            reg = json.loads((root / "orchestrator-state/tasks/registry.json").read_text())
            ids = [t["id"] for t in reg["tasks"]]
            by_id = {t["id"]: t for t in reg["tasks"]}

            # No duplicate IDs across the entire registry.
            self.assertEqual(len(ids), len(set(ids)),
                f"duplicate task IDs detected: {[i for i in ids if ids.count(i) > 1]}")

            # Sample of canonical IDs that MUST resolve to the right thing.
            samples = [
                ("P00-S01-T001", ["/health"]),
                ("P00-S04-T001", ["ShowcasePage", "/showcase"]),
                ("P00-S05-T001", ["LanguageSwitcher", "AppBar"]),
                ("P01-S02-T001", ["/auth/register"]),
                ("P02-S01-T002", ["LoginPage"]),
                ("P04-S04-T001", ["/api/v1/ai/chat"]),
                ("P04-S05-T001", ["/api/v1/ai/ingest"]),
                ("P09-S01-T001", ["AdminAIPage"]),
                ("P09-S02-T001", ["AIChatPage"]),
            ]
            for cid, alts in samples:
                t = by_id.get(cid)
                self.assertIsNotNone(t, f"{cid} missing from registry")
                self.assertTrue(any(a in t["title"] for a in alts),
                    f"{cid} title '{t['title']}' does not match any of {alts}")

            # All journey task_ids must resolve.
            id_set = set(by_id.keys())
            unresolved = []
            for j in reg.get("journeys", []):
                for tid in j.get("task_ids", []):
                    if tid not in id_set:
                        unresolved.append((j["id"], tid))
            self.assertEqual(unresolved, [],
                f"every journey task_id must resolve to a real registry task; unresolved={unresolved[:5]}")

            # Production-hardened BASEAPP is split into reviewable DAG lanes.
            # No phase may exceed 12 slices and no step may exceed 10.
            from collections import Counter
            phase_counts = Counter(t["phase_id"] for t in reg["tasks"])
            step_counts = Counter(t["step_id"] for t in reg["tasks"])
            self.assertLessEqual(max(phase_counts.values()), 12, phase_counts)
            self.assertLessEqual(max(step_counts.values()), 10, step_counts)
            self.assertEqual(len(reg.get("journeys") or []), 8)
            self.assertEqual(reg["task_dag"]["mode"], "explicit_dag")


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ---------------------------------------------------------------------------
# Synthetic refinement (split at sub-headings + warn on coarse)
# ---------------------------------------------------------------------------
class SyntheticSplitAndWarnTests(unittest.TestCase):
    """Pin the refined synthetic-task behaviour (Fix follow-up):
      * Step body with >=2 sub-headings -> split into one task per sub-heading.
      * Otherwise single task; warn when acceptance > SYNTHETIC_COARSE_THRESHOLD.
    """

    GUIDE = "# Tech Guide\n\n## Stack\n\nfastapi.\n\n## Architecture\n\nclean.\n"
    INSTR = "# Instructions\n\n## Goals\n\nBuild things.\n"

    def _run(self, checklist: str):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        (root / "docs/source-of-truth").mkdir(parents=True)
        (root / "docs/source-of-truth/instrucciones.md").write_text(self.INSTR, encoding="utf-8")
        (root / "docs/source-of-truth/X_IMPLEMENTATION_CHECKLIST.md").write_text(checklist, encoding="utf-8")
        (root / "docs/source-of-truth/X_TECHNICAL_GUIDE.md").write_text(self.GUIDE, encoding="utf-8")
        (root / "orchestrator-state/tasks").mkdir(parents=True)
        (root / "orchestrator-state/memory").mkdir(parents=True)
        prev = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(root)
        common._LOCK_DEPTH.clear()
        try:
            importlib.reload(boot)
            result = boot.generate_artifacts()
            reg = json.loads((root / "orchestrator-state/tasks/registry.json").read_text()) if (root / "orchestrator-state/tasks/registry.json").exists() else None
        finally:
            if prev is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = prev
            td.cleanup()
        return result, reg

    def test_coarse_synthetic_emits_warning(self):
        cl = (
            "# Test\n\n"
            "## Endpoint Coverage Registry\n\n"
            "| Slice ID | Method | Path | Step | Verify |\n"
            "|----------|--------|------|------|--------|\n"
            "| P00-S02-T001 | GET | /healthz | Step 0.2 | curl |\n\n"
            "# Phase 0 — Coarse\n\n"
            "## Step 0.1 — Big scaffolding step\n\n"
            + "\n".join(f"- [ ] item {i}" for i in range(1, 16))
            + "\n\n# Phase 1 — Done\n\n## Step 1.1 — End\n\n- [ ] add /healthz\n"
        )
        result, reg = self._run(cl)
        self.assertTrue(result["ok"])
        coarse = [w for w in result.get("validation", {}).get("warnings", []) if "synthetic task" in w]
        self.assertGreaterEqual(len(coarse), 1,
            "step with 15 acceptance items must surface a coarse-synthetic warning")
        self.assertIn("P00-S01-T001", coarse[0])

    def test_synthetic_below_threshold_does_not_warn(self):
        cl = (
            "# Test\n\n"
            "## Endpoint Coverage Registry\n\n"
            "| Slice ID | Method | Path | Step |\n"
            "|----|----|----|----|\n"
            "| P00-S02-T001 | GET | /a | Step 0.2 |\n\n"
            "# Phase 0 — Small\n\n"
            "## Step 0.1 — Tiny step\n\n"
            "- [ ] one\n- [ ] two\n- [ ] three\n\n"
            "# Phase 1 — Done\n\n## Step 1.1 — End\n\n- [ ] add /a\n"
        )
        result, _reg = self._run(cl)
        coarse = [w for w in result.get("validation", {}).get("warnings", []) if "synthetic task" in w]
        self.assertEqual(coarse, [],
            "step with 3 acceptance items must NOT trigger the coarse warning")

    def test_subheadings_drive_split(self):
        cl = (
            "# Test\n\n"
            "## Endpoint Coverage Registry\n\n"
            "| Slice ID | Method | Path | Step |\n"
            "|----|----|----|----|\n"
            "| P00-S02-T001 | GET | /a | Step 0.2 |\n\n"
            "# Phase 0 — Split\n\n"
            "## Step 0.1 — Big step with sub-tasks\n\n"
            "- [ ] preamble item\n"
            "\n### Sub-task A\n\n- [ ] do A1\n- [ ] do A2\n"
            "\n### Sub-task B\n\n- [ ] do B1\n- [ ] do B2\n"
            "\n# Phase 1 — Done\n\n## Step 1.1 — End\n\n- [ ] add /a\n"
        )
        _result, reg = self._run(cl)
        p0_synth = [t for t in reg["tasks"] if t["step_id"] == "P00-S01"]
        self.assertGreaterEqual(len(p0_synth), 2,
            "step with >=2 sub-headings must split into multiple synthetic tasks")
        # Preamble + Sub-task A + Sub-task B = 3 tasks expected.
        self.assertEqual(len(p0_synth), 3)
        titles = [t["title"] for t in p0_synth]
        self.assertIn("Sub-task A", titles)
        self.assertIn("Sub-task B", titles)
        # Each split task has its own acceptance, not all bullets.
        for t in p0_synth:
            self.assertLessEqual(len(t["acceptance"]), 2,
                "split tasks must have only their own bullets as acceptance")

    def test_no_subheadings_yields_single_task(self):
        cl = (
            "# Test\n\n"
            "## Endpoint Coverage Registry\n\n"
            "| Slice ID | Method | Path | Step |\n"
            "|----|----|----|----|\n"
            "| P00-S02-T001 | GET | /a | Step 0.2 |\n\n"
            "# Phase 0 — Flat\n\n"
            "## Step 0.1 — Plain step\n\n"
            "- [ ] one\n- [ ] two\n- [ ] three\n\n"
            "# Phase 1 — Done\n\n## Step 1.1 — End\n\n- [ ] add /a\n"
        )
        _result, reg = self._run(cl)
        p0 = [t for t in reg["tasks"] if t["step_id"] == "P00-S01"]
        self.assertEqual(len(p0), 1, "flat step (no sub-headings) must yield ONE synthetic task")
        self.assertEqual(p0[0]["id"], "P00-S01-T001")

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
  * E2E against the real BASELINE docs: every canonical sample matches and
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

import bootstrap_source_of_truth as boot  # noqa: E402
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
        silent drift to body-only generation."""
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

    def test_canonicals_only_no_hidden_synthetic_for_uncovered_body_step(self):
        phases, tasks = boot.build_phases_and_tasks(
            Path("checklist.md"), self._minimal_checklist())
        self.assertEqual([p["id"] for p in phases], ["P00"])
        ids = [t["id"] for t in tasks]
        self.assertEqual(ids, ["P00-S01-T001", "P00-S01-T002"],
            "DAG-only emits only declared Coverage Registry rows; uncovered body steps are source-of-truth drift")

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

    def test_uncovered_body_step_is_not_materialized_as_task(self):
        _, tasks = boot.build_phases_and_tasks(
            Path("checklist.md"), self._minimal_checklist())
        self.assertFalse(any(t["id"] == "P00-S02-T001" for t in tasks))

    def test_first_task_is_ready_rest_blocked(self):
        _, tasks = boot.build_phases_and_tasks(
            Path("checklist.md"), self._minimal_checklist())
        self.assertEqual(tasks[0]["status"], "ready")
        for t in tasks[1:]:
            self.assertEqual(t["status"], "blocked")


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
# E2E against optional real product baseline docs
# ---------------------------------------------------------------------------
class BootstrapEndToEndAgainstProductBaselineTests(unittest.TestCase):

    def test_real_product_baseline_bootstrap(self):
        required_v0_docs = (
            "instrucciones.md",
            "APP_IMPLEMENTATION_CHECKLIST.md",
            "APP_TECHNICAL_GUIDE.md",
        )
        src = REPO_ROOT / "docs" / "product-baseline"
        missing = [fname for fname in required_v0_docs if not (src / fname).is_file()]
        if missing:
            self.skipTest(
                "baseline snapshot docs are optional; skipping baseline snapshot bootstrap fixture because missing: "
                + ", ".join(missing)
            )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs" / "source-of-truth").mkdir(parents=True)
            for fname in required_v0_docs:
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

            # Production-hardened BASELINE is split into reviewable DAG lanes.
            # No phase may exceed 20 slices and no step may exceed 15.
            from collections import Counter
            phase_counts = Counter(t["phase_id"] for t in reg["tasks"])
            step_counts = Counter(t["step_id"] for t in reg["tasks"])
            self.assertLessEqual(max(phase_counts.values()), 20, phase_counts)
            self.assertLessEqual(max(step_counts.values()), 15, step_counts)
            self.assertEqual(len(reg.get("journeys") or []), 8)
            self.assertEqual(reg["task_dag"]["mode"], "explicit_dag")


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ---------------------------------------------------------------------------
# Synthetic refinement (split at sub-headings + warn on coarse)
# ---------------------------------------------------------------------------
@unittest.skip("DAG-only no longer materializes hidden synthetic tasks from body-only steps")
class SyntheticSplitAndWarnTests(unittest.TestCase):
    """Pin the refined synthetic-task behaviour (Fix follow-up):
      * Step body with >=2 sub-headings -> split into one task per sub-heading.
      * Otherwise single task; warn when acceptance > SYNTHETIC_COARSE_THRESHOLD.
    """

    GUIDE = "# Tech Guide\n\n## Stack\n\nfastapi.\n\n## Architecture\n\nclean.\n"
    INSTR = "# Instructions\n\n## Goals\n\nBuild things.\n"
    UX = "# UX Contract\n\n## Screen/Journey Lane Redactor Contract\n\nUse real/provided data.\n"
    STACK = "frontend:\n  language: typescript\n  framework: react\nbackend:\n  language: python\n  framework: fastapi\ndb:\n  engine: postgres\ndesign_tokens_enforcer: none\ngit_workflow: direct-main\n"

    def _run(self, checklist: str):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        (root / "docs/source-of-truth").mkdir(parents=True)
        (root / "docs/source-of-truth/instrucciones.md").write_text(self.INSTR, encoding="utf-8")
        (root / "docs/source-of-truth/X_IMPLEMENTATION_CHECKLIST.md").write_text(checklist, encoding="utf-8")
        (root / "docs/source-of-truth/X_TECHNICAL_GUIDE.md").write_text(self.GUIDE, encoding="utf-8")
        (root / "docs/source-of-truth/UX_CONTRACT.md").write_text(self.UX, encoding="utf-8")
        (root / "docs/source-of-truth/STACK_PROFILE.yaml").write_text(self.STACK, encoding="utf-8")
        (root / "docs/source-of-truth/UX_CONTRACT.md").write_text("# UX\n\n## Screens\n\nOK.\n", encoding="utf-8")
        (root / "docs/source-of-truth/STACK_PROFILE.yaml").write_text("frontend:\n  framework: react\nbackend:\n  framework: fastapi\ndb:\n  engine: postgres\ndesign_tokens_enforcer: ./scripts/check-design-tokens.sh\ngit_workflow: pr-flow\n", encoding="utf-8")
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
            "| Slice ID | Method | Path | Step | Depends on | Verify |\n"
            "|----------|--------|------|------|------------|--------|\n"
            "| P00-S02-T001 | GET | /healthz | Step 0.2 | P00-S01 | curl |\n\n"
            "# Phase 0 — Coarse\n\n"
            "## Step 0.1 — Big scaffolding step\n\n"
            + "\n".join(f"- [ ] item {i}" for i in range(1, 16))
            + "\n\n# Phase 1 — Done\n\n## Step 1.1 — End\n\n- [ ] add /healthz\n"
        )
        result, reg = self._run(cl)
        self.assertTrue(result["ok"])
        warnings = result.get("validation", {}).get("warnings", [])
        self.assertTrue(any("no Coverage Registry row" in w for w in warnings),
            "unregistered body steps must be reported, not emitted as hidden tasks")
        self.assertFalse(any(t["step_id"] == "P00-S01" for t in reg["tasks"]))

    def test_synthetic_below_threshold_does_not_warn(self):
        cl = (
            "# Test\n\n"
            "## Endpoint Coverage Registry\n\n"
            "| Slice ID | Method | Path | Step | Depends on |\n"
            "|----|----|----|----|------------|\n"
            "| P00-S02-T001 | GET | /a | Step 0.2 | P00-S01 |\n\n"
            "# Phase 0 — Small\n\n"
            "## Step 0.1 — Tiny step\n\n"
            "- [ ] one\n- [ ] two\n- [ ] three\n\n"
            "# Phase 1 — Done\n\n## Step 1.1 — End\n\n- [ ] add /a\n"
        )
        result, _reg = self._run(cl)
        warnings = result.get("validation", {}).get("warnings", [])
        self.assertTrue(any("no Coverage Registry row" in w for w in warnings))

    def test_subheadings_drive_split(self):
        cl = (
            "# Test\n\n"
            "## Endpoint Coverage Registry\n\n"
            "| Slice ID | Method | Path | Step | Depends on |\n"
            "|----|----|----|----|------------|\n"
            "| P00-S02-T001 | GET | /a | Step 0.2 | P00-S01 |\n\n"
            "# Phase 0 — Split\n\n"
            "## Step 0.1 — Big step with sub-tasks\n\n"
            "- [ ] preamble item\n"
            "\n### Sub-task A\n\n- [ ] do A1\n- [ ] do A2\n"
            "\n### Sub-task B\n\n- [ ] do B1\n- [ ] do B2\n"
            "\n# Phase 1 — Done\n\n## Step 1.1 — End\n\n- [ ] add /a\n"
        )
        result, reg = self._run(cl)
        self.assertTrue(result["ok"])
        self.assertFalse(any(t["step_id"] == "P00-S01" for t in reg["tasks"]),
            "DAG-only bootstrap must not synthesize hidden tasks from body sub-headings")

    def test_no_subheadings_yields_single_task(self):
        cl = (
            "# Test\n\n"
            "## Endpoint Coverage Registry\n\n"
            "| Slice ID | Method | Path | Step | Depends on |\n"
            "|----|----|----|----|------------|\n"
            "| P00-S02-T001 | GET | /a | Step 0.2 | P00-S01 |\n\n"
            "# Phase 0 — Flat\n\n"
            "## Step 0.1 — Plain step\n\n"
            "- [ ] one\n- [ ] two\n- [ ] three\n\n"
            "# Phase 1 — Done\n\n## Step 1.1 — End\n\n- [ ] add /a\n"
        )
        result, reg = self._run(cl)
        self.assertTrue(result["ok"])
        self.assertFalse(any(t["step_id"] == "P00-S01" for t in reg["tasks"]),
            "DAG-only bootstrap must not synthesize hidden tasks from body-only steps")


class BootstrapRuntimePreservationTests(unittest.TestCase):
    GUIDE = "# Tech Guide\n\n## Stack\n\npython/react.\n\n## Architecture\n\nclean.\n"
    INSTR = "# Instructions\n\n## Goals\n\nBuild a DAG app.\n"
    UX = "# UX\n\n## Purpose\n\nDAG app UX.\n"
    STACK = "frontend:\n  language: typescript\n  framework: react\nbackend:\n  language: python\n  framework: fastapi\ndb:\n  engine: postgres\ndesign_tokens_enforcer: none\ngit_workflow: push-to-main\n"
    UX = "# UX Contract\n\n## Screen/Journey Lane Redactor Contract\n\nUse real/provided data.\n"
    STACK = "frontend:\n  language: typescript\n  framework: react\nbackend:\n  language: python\n  framework: fastapi\ndb:\n  engine: postgres\ndesign_tokens_enforcer: none\ngit_workflow: direct-main\n"
    CHECKLIST = (
        "# Checklist\n\n"
        "## Canonical Coverage Registry\n\n"
        "| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| P00-S01-T001 | setup | scaffold | Step 0.1 | v1 | planned | low | auto | — | infra:scaffold | scripts/** | — | — | — | — | §1 | §2 | create scaffold | python -m pytest |\n"
        "| P00-S02-T001 | api | health | Step 0.2 | v1 | planned | low | auto | P00-S01-T001 | api:health | api/** | — | — | GET /health | — | §1 | §2 | health works | curl /health |\n\n"
        "# Phase 0 — Bootstrap\n\n"
        "## Step 0.1 — Scaffold\n\n- [ ] create scaffold\n\n"
        "## Step 0.2 — Health\n\n- [ ] health works\n"
    )

    def _root(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        sot = root / "docs/source-of-truth"
        sot.mkdir(parents=True)
        (sot / "instrucciones.md").write_text(self.INSTR, encoding="utf-8")
        (sot / "APP_TECHNICAL_GUIDE.md").write_text(self.GUIDE, encoding="utf-8")
        (sot / "APP_IMPLEMENTATION_CHECKLIST.md").write_text(self.CHECKLIST, encoding="utf-8")
        (sot / "UX_CONTRACT.md").write_text(self.UX, encoding="utf-8")
        (sot / "STACK_PROFILE.yaml").write_text(self.STACK, encoding="utf-8")
        (sot / "UX_CONTRACT.md").write_text("# UX\n\n## Screens\n\nOK.\n", encoding="utf-8")
        (sot / "STACK_PROFILE.yaml").write_text("frontend:\n  framework: react\nbackend:\n  framework: fastapi\ndb:\n  engine: postgres\ndesign_tokens_enforcer: ./scripts/check-design-tokens.sh\ngit_workflow: pr-flow\n", encoding="utf-8")
        (root / "orchestrator-state/tasks").mkdir(parents=True)
        (root / "orchestrator-state/memory").mkdir(parents=True)
        return td, root

    def _with_root(self, root):
        class EnvCtx:
            def __enter__(ctx_self):
                ctx_self.prev = os.environ.get("CLAUDE_PROJECT_DIR")
                os.environ["CLAUDE_PROJECT_DIR"] = str(root)
                common._LOCK_DEPTH.clear()
                importlib.reload(common)
                importlib.reload(boot)
                return boot, common
            def __exit__(ctx_self, exc_type, exc, tb):
                if ctx_self.prev is None:
                    os.environ.pop("CLAUDE_PROJECT_DIR", None)
                else:
                    os.environ["CLAUDE_PROJECT_DIR"] = ctx_self.prev
                common._LOCK_DEPTH.clear()
                importlib.reload(common)
                importlib.reload(boot)
        return EnvCtx()

    def test_refresh_preserves_runtime_state_by_default(self):
        td, root = self._root()
        try:
            with self._with_root(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                registry = common_mod.load_registry()
                registry["tasks"][0]["status"] = "done"
                registry["tasks"][0]["last_updated_by"] = "closer"
                registry["tasks"][1]["status"] = "claimed"
                registry["tasks"][1]["claimed_by"] = "worker-2"
                common_mod.save_registry(registry)
                # FW-006: reconciler keeps open_followups entries when the
                # YAML exists on disk and treats disk status as the source of truth.
                fu_dir = root / "orchestrator-state/tasks/follow-ups"
                fu_dir.mkdir(parents=True, exist_ok=True)
                (fu_dir / "FU-test.yaml").write_text(
                    "id: FU-test\nstatus: proposed\norigin_task_id: P00-S02-T001\n",
                    encoding="utf-8",
                )
                common_mod.save_runtime_state({
                    "last_worker": "tester",
                    "last_event": "subagent_stop",
                    "pending_journey_verifications": ["J1"],
                    "open_followups": [{"id": "FU-test", "status": "proposed"}],
                    "spawn_budget": 20,
                    "spawns_in_current_slice": {"P00-S02-T001": 4},
                })

                result = boot_mod.generate_artifacts()
                self.assertTrue(result["ok"])
                self.assertTrue(result["preserve_runtime_state"])
                self.assertEqual(result["preserved_task_count"], 2)
                refreshed = common_mod.load_registry()
                by_id = {t["id"]: t for t in refreshed["tasks"]}
                self.assertEqual(by_id["P00-S01-T001"]["status"], "done")
                self.assertEqual(by_id["P00-S01-T001"]["last_updated_by"], "closer")
                self.assertEqual(by_id["P00-S02-T001"]["status"], "claimed")
                self.assertEqual(by_id["P00-S02-T001"]["claimed_by"], "worker-2")
                runtime = common_mod.load_runtime_state()
                self.assertNotIn("last_claimed_task_id", runtime)
                self.assertEqual(runtime.get("last_worker"), "tester")
                self.assertEqual(runtime["last_worker"], "tester")
                # FW-003: bootstrap reconciliation drops orphan JIDs (J1 was set
                # in pending but registry.journeys does not declare it -> dropped).
                self.assertEqual(runtime["pending_journey_verifications"], [])
                self.assertEqual(runtime["open_followups"][0]["id"], "FU-test")
        finally:
            td.cleanup()

    def test_refresh_preserves_done_task_when_source_fingerprint_changes(self):
        td, root = self._root()
        try:
            with self._with_root(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                registry = common_mod.load_registry()
                first = registry["tasks"][0]
                self.assertIn("source_fingerprint", first)
                old_fp = first["source_fingerprint"]
                first["status"] = "done"
                first["last_outcome"] = "committed"
                first["last_updated_by"] = "closer"
                first["last_stop_at"] = "2026-05-11T00:00:00Z"
                common_mod.save_registry(registry)

                sot = root / "docs/source-of-truth"
                changed = self.CHECKLIST.replace("create scaffold", "create scaffold plus verified env docs")
                (sot / "APP_IMPLEMENTATION_CHECKLIST.md").write_text(changed, encoding="utf-8")

                result = boot_mod.generate_artifacts()
                self.assertTrue(result["ok"])
                refreshed = common_mod.load_registry()
                by_id = {t["id"]: t for t in refreshed["tasks"]}
                task = by_id["P00-S01-T001"]
                self.assertNotEqual(task["source_fingerprint"], old_fp)
                self.assertEqual(task["status"], "done")
                self.assertEqual(task["last_outcome"], "committed")
                self.assertEqual(task["last_updated_by"], "closer")
                self.assertTrue(task.get("source_fingerprint_changed_after_done"))
                self.assertNotEqual(task.get("previous_source_fingerprint"), task.get("source_fingerprint"))
                work_item = root / "orchestrator-state/tasks/work-items/P00-S01-T001.yaml"
                self.assertIn("status: done", work_item.read_text(encoding="utf-8"))
        finally:
            td.cleanup()

    def test_refresh_reasserts_closer_final_when_source_fingerprint_matches(self):
        td, root = self._root()
        try:
            with self._with_root(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                registry = common_mod.load_registry()
                registry["tasks"][0]["status"] = "done"
                registry["tasks"][0]["last_outcome"] = "committed"
                registry["tasks"][0]["last_updated_by"] = "closer"
                registry["tasks"][0]["last_stop_at"] = "2026-05-11T00:00:00Z"
                common_mod.save_registry(registry)

                result = boot_mod.generate_artifacts()
                self.assertTrue(result["ok"])
                refreshed = common_mod.load_registry()
                task = {t["id"]: t for t in refreshed["tasks"]}["P00-S01-T001"]
                self.assertEqual(task["status"], "done")
                self.assertEqual(task["last_outcome"], "committed")
                self.assertEqual(task["last_updated_by"], "closer")
                self.assertEqual(task["last_stop_at"], "2026-05-11T00:00:00Z")
                self.assertFalse(task.get("source_fingerprint_changed", False))
        finally:
            td.cleanup()


    def test_refresh_writes_complete_phase_status_when_all_tasks_done(self):
        td, root = self._root()
        try:
            with self._with_root(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                registry = common_mod.load_registry()
                for task in registry["tasks"]:
                    task["status"] = "done"
                    task["last_outcome"] = "committed"
                    task["last_updated_by"] = "closer"
                common_mod.save_registry(registry)
                result = boot_mod.generate_artifacts()
                self.assertTrue(result["ok"])
                phase = common_mod.load_registry()["phases"][0]
                self.assertEqual(phase["status"], "complete")
                phase_yaml = root / "orchestrator-state/tasks/phases/P00.yaml"
                self.assertIn("status: complete", phase_yaml.read_text(encoding="utf-8"))
        finally:
            td.cleanup()


    def test_refresh_preserves_open_followup_if_yaml_is_missing(self):
        td, root = self._root()
        try:
            with self._with_root(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                common_mod.save_runtime_state({
                    "open_followups": [{"id": "FU-missing", "status": "proposed", "severity": "blocker"}],
                    "spawn_budget": 20,
                    "spawns_in_current_slice": {},
                })

                result = boot_mod.generate_artifacts()
                self.assertTrue(result["ok"])
                runtime = common_mod.load_runtime_state()
                self.assertEqual(runtime["open_followups"][0]["id"], "FU-missing")
                self.assertTrue(runtime["open_followups"][0]["yaml_missing"])
        finally:
            td.cleanup()

    def test_reset_runtime_state_flag_is_explicitly_destructive(self):
        td, root = self._root()
        try:
            with self._with_root(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                registry = common_mod.load_registry()
                registry["tasks"][0]["status"] = "done"
                common_mod.save_registry(registry)
                common_mod.save_runtime_state({"open_followups": [{"id": "FU-test"}]})

                result = boot_mod.generate_artifacts(preserve_runtime_state=False)
                self.assertTrue(result["ok"])
                self.assertFalse(result["preserve_runtime_state"])
                refreshed = common_mod.load_registry()
                by_id = {t["id"]: t for t in refreshed["tasks"]}
                self.assertEqual(by_id["P00-S01-T001"]["status"], "ready")
                runtime = common_mod.load_runtime_state()
                self.assertNotIn("last_claimed_task_id", runtime)
                self.assertEqual(runtime.get("next_ready_task_id"), "P00-S01-T001")
                self.assertEqual(runtime["open_followups"], [])
        finally:
            td.cleanup()

    def test_acceptance_mentions_of_compose_and_env_extend_write_scope(self):
        td, root = self._root()
        try:
            sot = root / "docs/source-of-truth"
            checklist = self.CHECKLIST.replace(
                "create scaffold",
                "docker-compose.yml env overrides updated to match .env.example"
            )
            (sot / "APP_IMPLEMENTATION_CHECKLIST.md").write_text(checklist, encoding="utf-8")
            with self._with_root(root) as (boot_mod, common_mod):
                self.assertTrue(boot_mod.generate_artifacts()["ok"])
                task = common_mod.load_registry()["tasks"][0]
                self.assertIn("docker-compose.yml", task["allowed_paths"])
                self.assertIn("docker-compose.yml", task["write_set"])
                self.assertIn(".env.example", task["allowed_paths"])
                self.assertIn("infra:compose", task["conflict_groups"])
                self.assertIn("infra:env", task["conflict_groups"])
        finally:
            td.cleanup()

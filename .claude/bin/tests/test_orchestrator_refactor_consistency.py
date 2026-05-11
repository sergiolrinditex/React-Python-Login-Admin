from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_orchestrator_refactor_consistency_audit_passes():
    result = subprocess.run(
        ["python3", "-B", "-S", "scripts/audit-orchestrator-refactor-consistency.py"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ORCHESTRATOR_REFACTOR_CONSISTENCY_AUDIT: ok" in result.stdout


def test_github_workflow_never_promotes_optional_baseline_over_active_source_of_truth():
    workflow = (ROOT / ".github/workflows/orchestrator-tests.yml").read_text(encoding="utf-8")
    assert "cp docs/product-baseline" not in workflow
    # The separate negative test may empty source-of-truth intentionally;
    # the active bootstrap path must not copy/promote baseline over it.
    assert "Detect active source-of-truth" in workflow
    assert "present=false" in workflow
    assert "no active source-of-truth yet; use docs/templates to generate one" in workflow
    assert "test -s docs/source-of-truth/UX_CONTRACT.md" in workflow
    assert "test -s docs/source-of-truth/STACK_PROFILE.yaml" in workflow

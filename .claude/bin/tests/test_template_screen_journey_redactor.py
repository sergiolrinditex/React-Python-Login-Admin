from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load_smoke_module():
    path = ROOT / "scripts/smoke-template-profiles.py"
    spec = importlib.util.spec_from_file_location("smoke_template_profiles", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["smoke_template_profiles"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_template_screen_journey_redactor_audit_passes() -> None:
    proc = subprocess.run(
        ["python3", "-B", "-S", "scripts/audit-template-screen-journey-redactor.py"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout
    assert "TEMPLATE_SCREEN_JOURNEY_REDACTOR_AUDIT: ok" in proc.stdout


def test_all_15_templates_have_screen_journey_redactor_contract() -> None:
    files = [p for p in (ROOT / "docs/templates").rglob("*") if p.is_file() and p.suffix in {".md", ".yaml", ".yml"}]
    assert len(files) == 15
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "Screen/Journey Lane Redactor Contract" in text or "SCREEN_JOURNEY_REDACTOR_CONTRACT" in text, str(path)
        assert "screen/journey lane" in text.lower(), str(path)
        assert "journey" in text.lower(), str(path)


def test_smoke_generated_apps_are_grouped_by_screen_journey_lane_not_layer_phases() -> None:
    smoke = _load_smoke_module()
    forbidden = [
        "Phase 1 — API lane",
        "Phase 2 — UI lane",
        "Phase 3 — Journey gate",
        "SIN UI aún",
    ]
    for app in smoke.APPS:
        docs = smoke.build_docs(app)
        joined = "\n".join(docs.values())
        assert "Screen/Journey Lane Redactor Contract" in joined, app.name
        assert "screen/journey lane" in joined.lower(), app.name
        assert "connected screen" in joined.lower(), app.name
        assert "front -> back -> DB" in joined, app.name
        for needle in forbidden:
            assert needle not in joined, f"{app.name}: {needle}"


def test_checklists_keep_api_and_ui_under_named_screen_or_journey_refs() -> None:
    smoke = _load_smoke_module()
    for app in smoke.APPS:
        docs = smoke.build_docs(app)
        checklist_name = next(name for name in docs if name.endswith("_IMPLEMENTATION_CHECKLIST.md"))
        checklist = docs[checklist_name]
        # API/frontend tasks may exist, but must be anchored to a named journey and screen lane.
        for line in checklist.splitlines():
            if "| api |" in line or "| frontend |" in line or "| flutter |" in line:
                if "| v0 | done |" in line:
                    continue
                assert "screen-journey:" in line, f"{app.name}: {line}"
                assert "| J" in line, f"{app.name}: {line}"


def test_smoke_resets_runtime_state_before_bootstrap() -> None:
    smoke = (ROOT / "scripts/smoke-template-profiles.py").read_text(encoding="utf-8")
    assert "./scripts/reset-for-new-project.sh" in smoke
    assert "--reset-runtime-state" in smoke

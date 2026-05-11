from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REQUIRED_TEMPLATE_FILES = {
    "instrucciones.template.md",
    "PROJECT_TECHNICAL_GUIDE.template.md",
    "PROJECT_IMPLEMENTATION_CHECKLIST.template.md",
    "UX_CONTRACT.template.md",
    "STACK_PROFILE.template.yaml",
}
REQUIRED_COLUMNS = [
    "Slice ID", "Tipo", "Target", "Step", "Product increment", "Build state",
    "Risk level", "Verify mode", "Depends on", "Conflict group", "Write set",
    "Journey refs", "Pantalla/Ruta", "Endpoint", "Tablas DB", "Origen-Instr",
    "Origen-TechGuide", "Acceptance mínimo", "Verify mínimo",
]


def test_template_profiles_are_three_dirs_with_five_files_each():
    root = ROOT / "docs/templates"
    profiles = sorted(p.name for p in root.iterdir() if p.is_dir())
    loose_files = sorted(p.name for p in root.iterdir() if p.is_file())

    assert profiles == ["large-with-base", "large-without-base", "minimal"]
    assert loose_files == []
    for profile in profiles:
        found = {p.name for p in (root / profile).iterdir() if p.is_file()}
        assert found == REQUIRED_TEMPLATE_FILES, f"{profile} template files drifted: {sorted(found)}"


def test_minimal_template_keeps_same_dag_registry_contract():
    text = (ROOT / "docs/templates/minimal/PROJECT_IMPLEMENTATION_CHECKLIST.template.md").read_text(encoding="utf-8")
    assert "Canonical Coverage Registry" in text
    for col in REQUIRED_COLUMNS:
        assert col in text, f"minimal checklist missing {col}"
    assert "mode=explicit_dag" in text or "explicit_dag" in text
    assert "Runtime Follow-up Coverage Registry" in text


def test_large_with_base_profile_inherits_declared_baseline_stack():
    text = (ROOT / "docs/templates/large-with-base/STACK_PROFILE.template.yaml").read_text(encoding="utf-8")
    assert "{{frontend_framework}}" in text
    assert "{{backend_framework}}" in text
    assert "{{db_engine}}" in text
    assert "{{design_tokens_enforcer}}" in text
    assert "framework: flutter" not in text
    assert "framework: fastapi" not in text


def test_master_prompt_points_to_three_template_profiles():
    prompt = (ROOT / "docs/prompts/PROMPT_SOURCE_OF_TRUTH_DAG.md").read_text(encoding="utf-8")
    assert "large-with-base" in prompt
    assert "large-without-base" in prompt
    assert "minimal" in prompt
    assert "docs/templates/large-with-base" in prompt
    assert "docs/templates/large-without-base" in prompt
    assert "docs/templates/minimal" in prompt
    assert "5 source-of-truth" in prompt or "cinco source-of-truth" in prompt
    assert "mode=explicit_dag" in prompt

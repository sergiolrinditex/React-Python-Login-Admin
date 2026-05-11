from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_next_slice_repeats_dag_mode_before_plan_and_spawns() -> None:
    text = (ROOT / ".claude/commands/next-slice.md").read_text(encoding="utf-8")
    assert "## Production DAG mode" in text
    assert "MODO DAG ACTIVO: production = explicit_dag" in text
    assert "## Invariante DAG de esta ejecución" in text
    assert "RECORDATORIO DAG PARA ESTA EJECUCIÓN" in text
    assert "Cada Agent spawn debe recibir" in text
    assert "CLAUDE_TASK_PACK" in text
    assert "ausencia de `Depends on` es error operativo" in text


def test_templates_and_smoke_do_not_suggest_demo_seed_or_bundle_data() -> None:
    forbidden = [
        "datos demo",
        "dataset demo",
        "seed de datos",
        "seeds demo",
        "seed deterministic",
        "seed/fixture",
        "demo bundles",
        "prod-like",
        "prod_like",
        "datos fake",
        "PDFs sample",
        "lorem ipsum",
    ]
    paths = list((ROOT / "docs/templates").rglob("*")) + [ROOT / "scripts/smoke-template-profiles.py"]
    for path in paths:
        if not path.is_file() or path.suffix not in {".md", ".yaml", ".yml", ".py"}:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for needle in forbidden:
            assert needle.lower() not in text, f"{path}: {needle}"


def test_large_without_base_template_is_stack_and_domain_neutral() -> None:
    forbidden = [
        "flutter/f",
        "fastapi/s",
        "supabase storage",
        "contractuploadpage",
        "/contracts",
        "/api/v1/contracts",
        "contract_analysis_graph",
        "legal_corpus",
        "pdf_parser",
        "clause_extractor",
        "jurisprudencia",
    ]
    for path in (ROOT / "docs/templates/large-without-base").rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".yaml", ".yml"}:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for needle in forbidden:
            assert needle not in text, f"{path}: {needle}"


def test_templates_explain_phase_step_slice_sizing_without_over_fragmenting() -> None:
    for profile in ["minimal", "large-with-base", "large-without-base"]:
        path = ROOT / f"docs/templates/{profile}/PROJECT_IMPLEMENTATION_CHECKLIST.template.md"
        text = path.read_text(encoding="utf-8")
        assert "Modelo Phase / Step / Slice" in text
        assert "phase <=20 slices" in text
        assert "<=15 máximo" in text
        assert "No dividas un step coherente sólo por tener 11-12 slices" in text


def test_templates_say_missing_verification_data_must_be_provided() -> None:
    paths = [
        ROOT / "docs/templates/large-with-base/PROJECT_TECHNICAL_GUIDE.template.md",
        ROOT / "docs/templates/large-without-base/PROJECT_TECHNICAL_GUIDE.template.md",
        ROOT / "docs/templates/large-with-base/instrucciones.template.md",
        ROOT / "docs/templates/large-without-base/instrucciones.template.md",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "proporcion" in text.lower(), str(path)
        assert "si faltan datos" in text.lower() or "usuario/equipo proporcionará" in text.lower(), str(path)

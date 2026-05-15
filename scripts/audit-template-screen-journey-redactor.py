#!/usr/bin/env python3
"""Audit that templates steer generated apps by screen/journey lanes.

This prevents a common failure mode: source-of-truth generated as isolated
API/backend phases followed by UI phases and late UX polish. The production
DAG can contain API/backend/frontend slices, but each app-visible increment
must stay anchored to a named screen or journey lane.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "docs" / "templates"
EXPECTED_FILES = {
    "instrucciones.template.md",
    "PROJECT_TECHNICAL_GUIDE.template.md",
    "PROJECT_IMPLEMENTATION_CHECKLIST.template.md",
    "UX_CONTRACT.template.md",
    "STACK_PROFILE.template.yaml",
}
PROFILES = {"minimal", "large-with-base", "large-without-base"}
CONTRACT_MARKERS = [
    "Screen/Journey Lane Redactor Contract",
    "SCREEN_JOURNEY_REDACTOR_CONTRACT",
]
REQUIRED_IDEAS = [
    "screen/journey lane",
    "estados UX",
    "journey",
    "datos reales/proporcionados",
]
FORBIDDEN_LAYER_FIRST = [
    "SIN UI aún",
    "Phase 1 — API lane",
    "Phase 2 — UI lane",
    "Phase 3 — Journey gate",
]

FORBIDDEN_DOMAIN_LEAKAGE = [
    "legal-contract-analyzer",
    "contract_uploaded",
    "contract_analyzed",
    "contract_upload_page",
    "contract_list_page",
    "contracts/",
    "contracts table",
    "UploadPage",
    "AnalysisResultPage",
    "AnalysisDetailPage",
    "AnalysisListPage",
    "pypdf",
    "parse_pdf",
    "clause_classify",
    "jurisprudencia",
    "asesoramiento legal",
    "legalmente incorrectas",
]

STACK_SPECIFIC_TEMPLATE_LEAKAGE = [
    "`flutter` con la `<Page>`",
    "Tipo = flutter",
    "flutter analyze",
    "flutter build web",
    "frontend build web",
    "pytest api/tests",
    "`pytest ",
    "ruff check api",
    "mypy ",
    "alembic upgrade head",
    "ThemeData",
    "StatusBadge",
    "Auth completa",
    "Google OAuth",
    "test@user",
    "localhost:5000",
    "app/lib",
    "api/src",
]


def _fail(errors: list[str]) -> int:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1


def main() -> int:
    errors: list[str] = []
    if not TEMPLATE_ROOT.is_dir():
        return _fail([f"missing template root: {TEMPLATE_ROOT}"])

    profiles = {p.name for p in TEMPLATE_ROOT.iterdir() if p.is_dir()}
    if profiles != PROFILES:
        errors.append(f"docs/templates profiles mismatch: expected {sorted(PROFILES)}, got {sorted(profiles)}")

    files: list[Path] = []
    for profile in sorted(PROFILES):
        profile_dir = TEMPLATE_ROOT / profile
        current = {p.name for p in profile_dir.iterdir() if p.is_file()} if profile_dir.exists() else set()
        if current != EXPECTED_FILES:
            errors.append(f"{profile}: expected 5 template files {sorted(EXPECTED_FILES)}, got {sorted(current)}")
        files.extend(sorted(profile_dir.glob("*")))

    template_files = [p for p in files if p.is_file() and p.suffix in {".md", ".yaml", ".yml"}]
    if len(template_files) != 15:
        errors.append(f"expected exactly 15 template files, got {len(template_files)}")

    for path in template_files:
        text = path.read_text(encoding="utf-8")
        if not any(marker in text for marker in CONTRACT_MARKERS):
            errors.append(f"{path}: missing Screen/Journey Lane Redactor Contract")
        lowered = text.lower()
        for idea in REQUIRED_IDEAS:
            if idea.lower() not in lowered:
                errors.append(f"{path}: missing required idea {idea!r}")
        for forbidden in FORBIDDEN_LAYER_FIRST:
            if forbidden.lower() in lowered:
                errors.append(f"{path}: forbidden layer-first wording {forbidden!r}")
        if path.match("*/large-without-base/*") or path.match("*/large-with-base/*"):
            for forbidden in FORBIDDEN_DOMAIN_LEAKAGE:
                if forbidden.lower() in lowered:
                    errors.append(f"{path}: forbidden domain-specific template leakage {forbidden!r}")
            for forbidden in STACK_SPECIFIC_TEMPLATE_LEAKAGE:
                if forbidden.lower() in lowered:
                    errors.append(f"{path}: forbidden stack-specific template leakage {forbidden!r}")

    # The generated smoke docs are also part of the contract: they should not
    # generate apps as API-phase -> UI-phase -> UX-polish examples.
    smoke = ROOT / "scripts" / "smoke-template-profiles.py"
    if smoke.exists():
        smoke_text = smoke.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_LAYER_FIRST:
            if forbidden.lower() in smoke_text.lower():
                errors.append(f"{smoke}: forbidden layer-first wording {forbidden!r}")
        for expected in ["screen/journey lane", "connected screen", "journey verification"]:
            if expected not in smoke_text.lower():
                errors.append(f"{smoke}: missing smoke generation idea {expected!r}")
        if "./scripts/reset-for-new-project.sh" not in smoke_text or "--reset-runtime-state" not in smoke_text:
            errors.append(f"{smoke}: smoke projects must reset derived runtime state before bootstrapping")

    if errors:
        return _fail(errors)
    print("TEMPLATE_SCREEN_JOURNEY_REDACTOR_AUDIT: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

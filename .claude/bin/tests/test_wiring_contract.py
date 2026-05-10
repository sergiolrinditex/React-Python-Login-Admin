from __future__ import annotations

from pathlib import Path


def _write_three_docs(root: Path, endpoint_consumer: str = "ContractUploadPage / J101") -> None:
    sot = root / "docs" / "source-of-truth"
    sot.mkdir(parents=True, exist_ok=True)
    (sot / "instrucciones.md").write_text(
        """# Instrucciones

## 3.7 Journey Coverage Matrix

| ID | Milestone | Pantallas | Acciones | Endpoints | Tablas DB | Estado cliente | Slices | Verificación |
|----|-----------|-----------|----------|-----------|-----------|----------------|--------|--------------|
| J101 | M1 | ContractUploadPage → AnalysisResultsPage | upload, see analysis | `POST /api/v1/contracts/upload` | `contracts` | ContractUploadProvider | `P02-S02-T001`, `P03-S01-T001` | `/verify-journey J101` |
""",
        encoding="utf-8",
    )
    (sot / "APP_TECHNICAL_GUIDE.md").write_text(
        f"""# Technical Guide

## 6. Interfaces

### 6.1 Rutas Flutter nuevas

| Ruta | Page | Auth | Journey refs | Endpoints consumidos | Estado cliente/provider | Estados UI obligatorios | Next action | Slice ID | Descripción |
|------|------|------|--------------|----------------------|-------------------------|------------------------|-------------|----------|-------------|
| /contracts/upload | ContractUploadPage | Sí | J101 | POST /api/v1/contracts/upload | ContractUploadProvider | loading, error_network, success | /contracts/1/analysis | P03-S01-T001 | Upload |

### 6.2 Endpoints API nuevos

| Method | Path | Request | Response | Auth | Errors | Consumidor front/journey | Tablas/side effects | Slice ID |
|--------|------|---------|----------|------|--------|--------------------------|---------------------|----------|
| POST | /api/v1/contracts/upload | multipart file | {{data: {{contract_id}}}} | Sí | 400, 401 | {endpoint_consumer} | contracts | P02-S02-T001 |

### 6.5 Verification Data Contract

| Flow/Journey | Persona/Rol | Datos reales/proporcionados requeridos | Carga de datos reales/proporcionados permitida | Reset/Cleanup | Slices/Journeys |
|---|---|---|---|---|---|
| J101 | usuario QA contrato | usuario confirmado + PDF de contrato sandbox con cláusulas realistas | load_provided_contract_upload_data.sql | reset_hard + truncate contracts | P02-S02-T001, P03-S01-T001 / J101 |

## 10. Persistencia

### 10.3 Schema

contracts table
""",
        encoding="utf-8",
    )
    (sot / "APP_IMPLEMENTATION_CHECKLIST.md").write_text(
        """# Phase 0 — Bootstrap

## Canonical Coverage Registry

| Slice ID | Tipo | Target | Step | Product increment | Build state | Risk level | Verify mode | Depends on | Conflict group | Write set | Journey refs | Pantalla/Ruta | Endpoint | Tablas DB | Origen-Instr | Origen-TechGuide | Acceptance mínimo | Verify mínimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P02-S02-T001 | api | upload endpoint | Step 2.2 | v1 | planned | medium | human | — | api:contracts | api/src/**/contracts*.py; api/tests/**/contracts* | J101 | ContractUploadPage /contracts/upload | POST /api/v1/contracts/upload | contracts | §3.1 | §6.2 | endpoint works | curl |
| P03-S01-T001 | flutter | ContractUploadPage | Step 3.1 | v1 | planned | medium | human | P02-S02-T001 | front:contracts | app/lib/**/contracts*.dart; app/test/**/contracts* | J101 | ContractUploadPage /contracts/upload | POST /api/v1/contracts/upload | — | §3.2 | §6.1 | page works | flutter test |

## Step 2.2 — API
- [ ] upload endpoint
""",
        encoding="utf-8",
    )


def test_wiring_contract_accepts_filled_new_template(tmp_project):
    import check_wiring_contract

    _write_three_docs(tmp_project)
    result = check_wiring_contract.validate(tmp_project, require_new_template_columns=True)

    assert result["ok"], result
    assert result["counts"]["routes"] == 1
    assert result["counts"]["endpoints"] == 1
    assert result["counts"]["registry_rows"] == 2
    assert result["counts"]["journeys"] == 1
    assert result["counts"]["verification_data_contract"] == 1


def test_wiring_contract_requires_endpoint_consumer_when_requested(tmp_project):
    import check_wiring_contract

    _write_three_docs(tmp_project, endpoint_consumer="")
    result = check_wiring_contract.validate(tmp_project, require_new_template_columns=True)

    assert not result["ok"]
    assert any("missing Consumidor front/journey" in err for err in result["errors"])


def test_wiring_contract_requires_verification_data_contract_for_new_templates(tmp_project):
    import check_wiring_contract

    _write_three_docs(tmp_project)
    guide = tmp_project / "docs" / "source-of-truth" / "APP_TECHNICAL_GUIDE.md"
    text = guide.read_text(encoding="utf-8")
    start = text.index("### 6.5 Verification Data Contract")
    end = text.index("## 10. Persistencia")
    guide.write_text(text[:start] + text[end:], encoding="utf-8")

    result = check_wiring_contract.validate(tmp_project, require_new_template_columns=True)

    assert not result["ok"]
    assert any("Verification Data Contract" in err for err in result["errors"])

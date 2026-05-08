from __future__ import annotations

import json


def test_generate_api_contracts_creates_openapi_and_frontend_stubs(tmp_project):
    import common
    import generate_api_contracts

    tasks = [
        {
            "id": "P01-S01-T001",
            "title": "Item detail",
            "kind": "api",
            "status": "ready",
            "depends_on": [],
            "endpoint": "GET /api/v1/items/{id}",
            "journey_refs": ["J1"],
            "tables": ["items"],
            "route": "/items/:id",
        },
        {
            "id": "P01-S02-T001",
            "title": "Create item",
            "kind": "api",
            "status": "ready",
            "depends_on": [],
            "endpoint": "POST /api/v1/items",
            "journey_refs": ["J1"],
            "tables": ["items"],
            "route": "/items/new",
        },
    ]
    common.save_registry({
        "generated_at": common.now_iso(),
        "project_prefix": "ITEMS",
        "tasks": tasks,
        "phases": [],
        "journeys": [],
        "task_dag": {"source_digest": "seed"},
    })

    result = generate_api_contracts.generate_contracts(validate_only=False)
    assert result["ok"] is True
    assert result["endpoint_count"] == 2

    contracts = tmp_project / "orchestrator-state" / "tasks" / "api-contracts"
    openapi = json.loads((contracts / "openapi.json").read_text(encoding="utf-8"))
    assert "/api/v1/items/{id}" in openapi["paths"]
    assert "get" in openapi["paths"]["/api/v1/items/{id}"]
    assert "/api/v1/items" in openapi["paths"]
    assert "post" in openapi["paths"]["/api/v1/items"]

    ts = (contracts / "frontend" / "typescript" / "apiClient.generated.ts").read_text(encoding="utf-8")
    dart = (contracts / "frontend" / "dart" / "api_client.g.dart").read_text(encoding="utf-8")
    assert "API_ENDPOINTS" in ts
    assert "buildPath" in ts
    assert "apiEndpoints" in dart
    assert "buildApiPath" in dart

    fresh = generate_api_contracts.generate_contracts(validate_only=True)
    assert fresh["ok"] is True

    registry = common.load_registry()
    registry["tasks"][0]["endpoint"] = "GET /api/v1/items/{id}/audit"
    common.save_registry(registry)
    stale = generate_api_contracts.generate_contracts(validate_only=True)
    assert stale["ok"] is False


def test_validate_only_skips_when_registry_missing(tmp_project):
    import common
    import generate_api_contracts

    path = common.registry_path()
    if path.exists():
        path.unlink()
    result = generate_api_contracts.generate_contracts(validate_only=True)
    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["reason"] == "registry_missing"

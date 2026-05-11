#!/usr/bin/env python3
"""Generate front/back API contract artifacts from the Coverage Registry.

The registry is the single runtime source of truth for endpoints. This script
materializes a small OpenAPI document plus frontend stubs so frontend/backend
drift is visible and testable instead of relying on prompts remembering it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from common import load_registry, now_iso, registry_path, relpath, tasks_dir, write_json, write_text

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
ENDPOINT_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)(?:/([A-Z/]+))?\s+(/[^\s,;`|]+)", re.I)
NONE_VALUES = {"", "-", "—", "none", "n/a", "na", "null", "sin endpoint"}


def _clean(value: Any) -> str:
    return str(value or "").replace("`", "").strip()


def _norm_path(path: str) -> str:
    path = _clean(path)
    path = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", path)
    return path


def _tokens(value: Any) -> list[tuple[str, str]]:
    text = _clean(value)
    if text.lower() in NONE_VALUES:
        return []
    out: list[tuple[str, str]] = []
    for method, more_methods, path in ENDPOINT_RE.findall(text):
        methods = [method.upper()]
        if more_methods:
            methods.extend(m.upper() for m in more_methods.split("/") if m.strip())
        for m in methods:
            if m in METHODS:
                item = (m, _norm_path(path))
                if item not in out:
                    out.append(item)
    return out


def _path_params(path: str) -> list[str]:
    return re.findall(r"{([A-Za-z_][A-Za-z0-9_]*)}", path)


def _pascal(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", value)
    return "".join(w[:1].upper() + w[1:] for w in words) or "Endpoint"


def _camel(value: str) -> str:
    name = _pascal(value)
    return name[:1].lower() + name[1:]


def _operation_id(method: str, path: str) -> str:
    base = f"{method.lower()} {path}"
    return _camel(base)


def _schema_name(method: str, path: str, suffix: str) -> str:
    return _pascal(f"{method.lower()} {path} {suffix}")


def extract_registry_endpoints(registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    registry = registry or load_registry()
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for task in registry.get("tasks", []) or []:
        raw_values = [task.get("endpoint"), task.get("endpoint_raw"), task.get("target")]
        for raw in raw_values:
            for method, path in _tokens(raw):
                key = (method, path)
                entry = seen.setdefault(key, {
                    "method": method,
                    "path": path,
                    "operation_id": _operation_id(method, path),
                    "request_schema": _schema_name(method, path, "Request"),
                    "response_schema": _schema_name(method, path, "Response"),
                    "path_params": _path_params(path),
                    "slice_ids": [],
                    "journey_refs": [],
                    "tables": [],
                    "routes": [],
                    "first_task_kind": task.get("kind") or task.get("tipo") or "unspecified",
                })
                sid = str(task.get("id") or "").strip()
                if sid and sid not in entry["slice_ids"]:
                    entry["slice_ids"].append(sid)
                for jid in task.get("journey_refs") or []:
                    jid = str(jid).strip()
                    if jid and jid not in entry["journey_refs"]:
                        entry["journey_refs"].append(jid)
                for table in task.get("tables") or []:
                    table = str(table).strip()
                    if table and table not in entry["tables"]:
                        entry["tables"].append(table)
                route = str(task.get("route") or "").strip()
                if route and route not in entry["routes"]:
                    entry["routes"].append(route)
    return sorted(seen.values(), key=lambda e: (e["path"], METHODS.index(e["method"]) if e["method"] in METHODS else 99))


def _json_schema_ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def build_openapi(registry: dict[str, Any], endpoints: list[dict[str, Any]]) -> dict[str, Any]:
    paths: dict[str, Any] = {}
    schemas: dict[str, Any] = {
        "GenericJson": {
            "type": "object",
            "additionalProperties": True,
            "description": "Generated placeholder schema. Replace with explicit DTO schema in the Technical Guide when available.",
        },
        "ErrorResponse": {
            "type": "object",
            "properties": {"detail": {"type": "string"}},
            "additionalProperties": True,
        },
    }
    for ep in endpoints:
        method = ep["method"].lower()
        path_item = paths.setdefault(ep["path"], {})
        request_name = ep["request_schema"]
        response_name = ep["response_schema"]
        schemas.setdefault(request_name, {"allOf": [_json_schema_ref("GenericJson")], "x-generated-from": ep["slice_ids"]})
        schemas.setdefault(response_name, {"allOf": [_json_schema_ref("GenericJson")], "x-generated-from": ep["slice_ids"]})
        op: dict[str, Any] = {
            "operationId": ep["operation_id"],
            "tags": [ep.get("first_task_kind") or "api"],
            "x-slice-ids": ep["slice_ids"],
            "x-journey-refs": ep["journey_refs"],
            "x-tables": ep["tables"],
            "parameters": [
                {"name": name, "in": "path", "required": True, "schema": {"type": "string"}}
                for name in ep["path_params"]
            ],
            "responses": {
                "200": {
                    "description": "OK",
                    "content": {"application/json": {"schema": _json_schema_ref(response_name)}},
                },
                "4XX": {"description": "Client error", "content": {"application/json": {"schema": _json_schema_ref("ErrorResponse")}}},
                "5XX": {"description": "Server error", "content": {"application/json": {"schema": _json_schema_ref("ErrorResponse")}}},
            },
        }
        if ep["method"] not in {"GET", "HEAD", "DELETE"}:
            op["requestBody"] = {
                "required": False,
                "content": {"application/json": {"schema": _json_schema_ref(request_name)}},
            }
        path_item[method] = op
    return {
        "openapi": "3.1.0",
        "info": {
            "title": f"{registry.get('project_prefix') or 'APP'} generated API contract",
            "version": "generated-from-coverage-registry",
            "description": "Generated by .claude/bin/generate_api_contracts.py from orchestrator-state/tasks/registry.json.",
        },
        "paths": paths,
        "components": {"schemas": schemas},
    }


def _digest_payload(registry: dict[str, Any], endpoints: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "project_prefix": registry.get("project_prefix"),
        "task_dag_source_digest": (registry.get("task_dag") or {}).get("source_digest"),
        "endpoints": endpoints,
    }


def _digest(payload: Any) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _json_as_yaml(data: Any) -> str:
    # JSON is a YAML subset and keeps the generator dependency-free.
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _ts_name(ep: dict[str, Any]) -> str:
    return ep["operation_id"]


def _dart_name(ep: dict[str, Any]) -> str:
    name = ep["operation_id"]
    if name in {"get", "post", "put", "patch", "delete", "class", "switch", "default"}:
        name += "Endpoint"
    return name


def render_typescript(endpoints: list[dict[str, Any]]) -> str:
    lines = [
        "// GENERATED FILE - do not edit by hand.",
        "// Source: orchestrator-state/tasks/api-contracts/openapi.json",
        "export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };",
        "export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD' | 'OPTIONS';",
        "export interface ApiEndpointMeta { operationId: string; method: HttpMethod; path: string; sliceIds: string[]; journeyRefs: string[]; pathParams: string[]; }",
        "export const API_ENDPOINTS: ApiEndpointMeta[] = [",
    ]
    for ep in endpoints:
        lines.append("  " + json.dumps({
            "operationId": ep["operation_id"],
            "method": ep["method"],
            "path": ep["path"],
            "sliceIds": ep["slice_ids"],
            "journeyRefs": ep["journey_refs"],
            "pathParams": ep["path_params"],
        }, ensure_ascii=False) + ",")
    lines.extend([
        "];",
        "export function buildPath(path: string, params: Record<string, string | number> = {}): string {",
        "  return path.replace(/\\{([^}]+)\\}/g, (_m, key) => encodeURIComponent(String(params[key] ?? '')));",
        "}",
        "export interface ApiClientOptions { baseUrl?: string; fetchImpl?: typeof fetch; defaultHeaders?: Record<string, string>; }",
        "export class ApiClient {",
        "  constructor(private readonly opts: ApiClientOptions = {}) {}",
        "  async request<T = Json>(meta: ApiEndpointMeta, args: { pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; } = {}): Promise<T> {",
        "    const fetcher = this.opts.fetchImpl ?? fetch;",
        "    const url = new URL((this.opts.baseUrl ?? '') + buildPath(meta.path, args.pathParams));",
        "    for (const [key, value] of Object.entries(args.query ?? {})) if (value !== undefined) url.searchParams.set(key, String(value));",
        "    const res = await fetcher(url.toString(), { method: meta.method, headers: { 'content-type': 'application/json', ...(this.opts.defaultHeaders ?? {}), ...(args.headers ?? {}) }, body: args.body === undefined ? undefined : JSON.stringify(args.body) });",
        "    if (!res.ok) throw new Error(`${meta.method} ${meta.path} failed with ${res.status}`);",
        "    return (await res.json()) as T;",
        "  }",
    ])
    for i, ep in enumerate(endpoints):
        lines.append(f"  {_ts_name(ep)}(args: {{ pathParams?: Record<string, string | number>; query?: Record<string, string | number | boolean | undefined>; body?: Json; headers?: Record<string, string>; }} = {{}}) {{")
        lines.append(f"    return this.request(API_ENDPOINTS[{i}], args);")
        lines.append("  }")
    lines.extend(["}", ""])
    return "\n".join(lines)


def render_dart(endpoints: list[dict[str, Any]]) -> str:
    lines = [
        "// GENERATED FILE - do not edit by hand.",
        "// Source: orchestrator-state/tasks/api-contracts/openapi.json",
        "class ApiEndpointMeta {",
        "  const ApiEndpointMeta({required this.operationId, required this.method, required this.path, required this.sliceIds, required this.journeyRefs, required this.pathParams});",
        "  final String operationId;",
        "  final String method;",
        "  final String path;",
        "  final List<String> sliceIds;",
        "  final List<String> journeyRefs;",
        "  final List<String> pathParams;",
        "}",
        "String buildApiPath(String path, Map<String, Object?> params) {",
        "  var out = path;",
        "  params.forEach((key, value) { out = out.replaceAll('{$key}', Uri.encodeComponent(value.toString())); });",
        "  return out;",
        "}",
        "const apiEndpoints = <ApiEndpointMeta>[",
    ]
    for ep in endpoints:
        lines.append(
            "  ApiEndpointMeta(operationId: " + json.dumps(ep["operation_id"]) +
            ", method: " + json.dumps(ep["method"]) +
            ", path: " + json.dumps(ep["path"]) +
            ", sliceIds: " + json.dumps(ep["slice_ids"]) +
            ", journeyRefs: " + json.dumps(ep["journey_refs"]) +
            ", pathParams: " + json.dumps(ep["path_params"]) + "),"
        )
    lines.extend([
        "];",
        "abstract class ApiTransport {",
        "  Future<Map<String, dynamic>> send(ApiEndpointMeta endpoint, {Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body});",
        "}",
        "class ApiClient {",
        "  ApiClient(this.transport);",
        "  final ApiTransport transport;",
        "  Future<Map<String, dynamic>> requestByOperation(String operationId, {Map<String, Object?> pathParams = const {}, Map<String, Object?> query = const {}, Object? body}) {",
        "    final endpoint = apiEndpoints.firstWhere((e) => e.operationId == operationId);",
        "    return transport.send(endpoint, pathParams: pathParams, query: query, body: body);",
        "  }",
    ])
    for ep in endpoints:
        lines.append(f"  Future<Map<String, dynamic>> {_dart_name(ep)}({{Map<String, Object?> pathParams = const {{}}, Map<String, Object?> query = const {{}}, Object? body}}) {{")
        lines.append(f"    return requestByOperation('{ep['operation_id']}', pathParams: pathParams, query: query, body: body);")
        lines.append("  }")
    lines.extend(["}", ""])
    return "\n".join(lines)


def generate_contracts(*, validate_only: bool = False) -> dict[str, Any]:
    # A freshly unpacked/just-reset orchestrator may not have a generated
    # registry yet. In validate-only mode this is not API-contract drift; it
    # simply means bootstrap has not materialized runtime state. Keep
    # run-all-tests.sh usable on a clean zip and let bootstrap/check scripts own
    # source-of-truth validation.
    if validate_only and not registry_path().exists():
        return {
            "ok": True,
            "skipped": True,
            "reason": "registry_missing",
            "endpoint_count": 0,
            "artifacts_dir": relpath(tasks_dir() / "api-contracts"),
        }
    registry = load_registry()
    endpoints = extract_registry_endpoints(registry)
    payload = _digest_payload(registry, endpoints)
    expected = _digest(payload)
    root = tasks_dir() / "api-contracts"
    manifest_path = root / "CONTRACT_MANIFEST.json"
    actual = None
    if manifest_path.exists():
        try:
            actual = json.loads(manifest_path.read_text(encoding="utf-8")).get("source_digest")
        except Exception:
            actual = None
    if validate_only:
        return {
            "ok": expected == actual,
            "expected_digest": expected,
            "actual_digest": actual,
            "endpoint_count": len(endpoints),
            "artifacts_dir": relpath(root),
        }
    openapi = build_openapi(registry, endpoints)
    root.mkdir(parents=True, exist_ok=True)
    (root / "frontend" / "typescript").mkdir(parents=True, exist_ok=True)
    (root / "frontend" / "dart").mkdir(parents=True, exist_ok=True)
    write_json(root / "registry-endpoints.json", {"generated_at": now_iso(), "endpoints": endpoints})
    write_json(root / "openapi.json", openapi)
    write_text(root / "openapi.yaml", _json_as_yaml(openapi))
    write_text(root / "frontend" / "typescript" / "apiClient.generated.ts", render_typescript(endpoints))
    write_text(root / "frontend" / "dart" / "api_client.g.dart", render_dart(endpoints))
    manifest = {
        "generated_at": now_iso(),
        "generator": relpath(Path(__file__)),
        "source": relpath(tasks_dir() / "registry.json"),
        "source_digest": expected,
        "endpoint_count": len(endpoints),
        "artifacts": [
            relpath(root / "registry-endpoints.json"),
            relpath(root / "openapi.json"),
            relpath(root / "openapi.yaml"),
            relpath(root / "frontend" / "typescript" / "apiClient.generated.ts"),
            relpath(root / "frontend" / "dart" / "api_client.g.dart"),
        ],
    }
    write_json(manifest_path, manifest)
    return {"ok": True, **manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate OpenAPI and frontend stubs from orchestrator registry endpoints.")
    parser.add_argument("--validate-only", action="store_true", help="Fail if generated artifacts are stale or missing.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = generate_contracts(validate_only=args.validate_only)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result.get("ok"):
            if args.validate_only:
                if result.get("skipped"):
                    print("API contracts check skipped — registry.json missing; run bootstrap to materialize contracts.")
                else:
                    print(f"API contracts up to date — endpoints={result.get('endpoint_count')}")
            else:
                print(f"Generated API contracts — endpoints={result.get('endpoint_count')} dir={result.get('artifacts_dir', 'orchestrator-state/tasks/api-contracts')}")
        else:
            print("API contracts stale or missing. Run ./scripts/generate-api-contracts.sh")
            print(f"expected={result.get('expected_digest')} actual={result.get('actual_digest')}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

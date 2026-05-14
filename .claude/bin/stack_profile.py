#!/usr/bin/env python3
"""Load the declarative stack profile for this project.

The orchestrator engine is stack-agnostic. Concrete paths and commands live in
`docs/source-of-truth/STACK_PROFILE.yaml` (or `docs/product-baseline/STACK_PROFILE.yaml`
for an already-built baseline). This parser intentionally supports only the
small YAML subset used by the template: nested mappings and scalar/list values.
It avoids external dependencies so hooks and CI can run in a fresh checkout.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

DEFAULT_PROFILE: dict[str, Any] = {
    "profile_version": "stack-profile-v1",
    "frontend": {
        "language": "none",
        "framework": "none",
        "module_root": "none",
        "theme_root": "none",
        "test_cmd": "none",
        "dev_cmd": "none",
        "visual_check": "none",
    },
    "backend": {
        "language": "none",
        "framework": "none",
        "module_root": "none",
        "test_cmd": "none",
        "dev_cmd": "none",
        "health_url": "none",
    },
    "db": {
        "engine": "none",
        "migrate_cmd": "none",
        "seed_cmd": "none",
    },
    "git_workflow": "push-to-main",
    "git_identity": {
        "user_name": "",
        "user_email": "",
        "github_login": "",
    },
    "design_tokens_enforcer": "none",
}



def project_root() -> Path:
    explicit = os.environ.get("CLAUDE_ORCHESTRATOR_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR")
    if explicit:
        return Path(explicit).resolve()
    return Path(__file__).resolve().parents[2]


def _strip_comment(value: str) -> str:
    in_single = False
    in_double = False
    out = []
    prev = ""
    for ch in value:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single and prev != "\\":
            in_double = not in_double
        if ch == "#" and not in_single and not in_double:
            break
        out.append(ch)
        prev = ch
    return "".join(out).rstrip()


def _parse_scalar(value: str) -> Any:
    value = _strip_comment(value).strip()
    if value in {"", "null", "Null", "NULL", "~"}:
        return ""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        if not body:
            return []
        return [_parse_scalar(part.strip()) for part in body.split(",")]
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except Exception:
            return value
    return value


def parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.rstrip().startswith("---"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = _strip_comment(raw).strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1] if stack else root
        if value == "":
            node: dict[str, Any] = {}
            parent[key] = node
            stack.append((indent, node))
        else:
            parent[key] = _parse_scalar(value)
    return root


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(base))
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def find_stack_profile(root: Path | None = None) -> Path | None:
    root = root or project_root()
    for rel in ("docs/source-of-truth/STACK_PROFILE.yaml", "docs/product-baseline/STACK_PROFILE.yaml"):
        path = root / rel
        if path.is_file():
            return path
    return None


def load_stack_profile(root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    path = find_stack_profile(root)
    if not path:
        profile = json.loads(json.dumps(DEFAULT_PROFILE))
        profile["_source"] = "default:none"
        return profile
    parsed = parse_simple_yaml(path.read_text(encoding="utf-8"))
    profile = deep_merge(DEFAULT_PROFILE, parsed)
    profile["_source"] = str(path.relative_to(root))
    return profile


def get_path(profile: dict[str, Any], dotted: str, default: Any = None) -> Any:
    current: Any = profile
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def main() -> int:
    parser = argparse.ArgumentParser(description="Read docs/source-of-truth/STACK_PROFILE.yaml")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--get", help="Dotted key, e.g. frontend.module_root")
    parser.add_argument("--default", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    profile = load_stack_profile(args.root.resolve() if args.root else None)
    if args.get:
        value = get_path(profile, args.get, args.default)
        if args.json:
            print(json.dumps(value, ensure_ascii=False))
        elif isinstance(value, (dict, list)):
            print(json.dumps(value, ensure_ascii=False))
        else:
            print(value)
        return 0
    print(json.dumps(profile, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    end = text.find("\n---", 4)
    assert end != -1
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def test_project_defaults_to_main_orchestrator_main_thread() -> None:
    settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    assert settings.get("agent") == "main-orchestrator"


def test_main_orchestrator_inherits_all_tools_instead_of_allowlisting() -> None:
    path = ROOT / ".claude/agents/main-orchestrator.md"
    fm = _frontmatter(path)
    assert "tools" not in fm
    assert "disallowedTools" not in fm

    text = path.read_text(encoding="utf-8")
    assert "## Main-thread agent contract" in text
    assert "No añadas `tools:` ni `disallowedTools:`" in text
    assert "hereda todas las herramientas disponibles" in text
    assert "claude --agent main-orchestrator --permission-mode bypassPermissions" in text

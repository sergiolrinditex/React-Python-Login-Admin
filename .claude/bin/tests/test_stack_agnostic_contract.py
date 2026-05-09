from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_design_token_enforcer_public_contract_is_agnostic():
    enforcers = ROOT / ".claude" / "enforcers"
    assert (enforcers / "design_tokens_v1.sh").exists()
    assert (enforcers / "design_tokens_v1" / "RULES.md").exists()
    assert (enforcers / "none.sh").exists()
    assert not (enforcers / "flutter_v1.sh").exists()
    assert not (enforcers / "react_v1.sh").exists()
    assert not (enforcers / "swiftui_v1.sh").exists()


def test_stack_profiles_use_capability_named_enforcer():
    optional_baseapp_profile = ROOT / "docs/base-app/STACK_PROFILE.yaml"
    paths = [
        ROOT / "docs/source-of-truth/STACK_PROFILE.yaml",
        ROOT / "docs/templates/minimal/STACK_PROFILE.template.yaml",
        ROOT / "docs/templates/large-with-base/STACK_PROFILE.template.yaml",
        ROOT / "docs/templates/large-without-base/STACK_PROFILE.template.yaml",
    ]
    if optional_baseapp_profile.exists():
        paths.append(optional_baseapp_profile)
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "design_tokens_v1" in text or "{{design_tokens_enforcer}}" in text
        assert "flutter_v1" not in text
        assert "react_v1" not in text
        assert "swiftui_v1" not in text


def test_large_with_base_stack_profile_is_not_anystack_free():
    text = (ROOT / "docs/templates/large-with-base/STACK_PROFILE.template.yaml").read_text(encoding="utf-8")
    assert "framework: flutter" in text
    assert "framework: fastapi" in text
    assert "engine: postgres" in text
    assert "module_root: app/lib" in text
    assert "module_root: api/src" in text


def test_stack_profile_default_is_neutral():
    result = subprocess.run(
        [sys.executable, "-B", "-S", str(ROOT / ".claude" / "bin" / "stack_profile.py"), "--root", str(ROOT / "__missing_root__"), "--json"],
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    profile = json.loads(result.stdout)
    assert profile["frontend"]["framework"] == "none"
    assert profile["backend"]["framework"] == "none"
    assert profile["db"]["engine"] == "none"
    assert profile["design_tokens_enforcer"] == "none"


def test_prompt_declares_all_template_profiles():
    prompt = (ROOT / "docs/prompts/PROMPT_SOURCE_OF_TRUTH_DAG.md").read_text(encoding="utf-8")
    assert "large-with-base" in prompt
    assert "large-without-base" in prompt
    assert "minimal" in prompt
    assert "design_tokens_v1" in prompt

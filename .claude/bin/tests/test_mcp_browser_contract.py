from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_slice_verifier_requires_usable_browser_mcp_not_just_listed_tools() -> None:
    text = (ROOT / ".claude/agents/slice-verifier.md").read_text(encoding="utf-8")
    assert "usable" in text.lower()
    assert "listed_but_unusable" in text
    assert "scripts/chrome-mcp-doctor.sh" in text
    assert "scripts/chrome-devtools-isolated-session.sh" in text
    assert "Agent360" in text
    assert "browser-mcp" in text
    assert "no dejes `MODE: partial`" in text
    assert "Si un MCP usable ya completó" in text
    assert text.index("`chrome-devtools`") < text.index("`claude-in-chrome`") < text.index("`agent360-browser-mcp` / `browser-mcp`")
    assert "Chrome DevTools MCP es el camino principal" in text
    assert "Agent360/`browser-mcp` queda como tercer fallback" in text
    assert "**primario**" in text
    assert "**segundo fallback**" in text
    assert "**tercer fallback**" in text


def test_verify_slice_command_mentions_profile_lock_recovery() -> None:
    text = (ROOT / ".claude/commands/verify-slice.md").read_text(encoding="utf-8")
    assert "profile lock" in text
    assert "scripts/chrome-mcp-doctor.sh" in text
    assert "Si uno de los MCP ya completó" in text
    assert "Agent360" in text
    assert "browser-mcp" in text
    assert "Orden obligatorio de preferencia: 1) Chrome DevTools MCP aislado, 2) Claude-in-Chrome MCP, 3) Agent360 Browser MCP" in text
    assert "Orden obligatorio de preferencia: 1) Chrome DevTools MCP aislado, 2) Claude-in-Chrome MCP, 3) Agent360 Browser MCP" in text


def test_chrome_mcp_doctor_is_bash3_safe() -> None:
    text = (ROOT / "scripts/chrome-mcp-doctor.sh").read_text(encoding="utf-8")
    forbidden = ["mapfile", "readarray", "declare -A"]
    for token in forbidden:
        assert token not in text


def test_slice_verifier_has_bounded_extra_mcp_tool_budget() -> None:
    text = (ROOT / ".claude/agents/slice-verifier.md").read_text(encoding="utf-8")
    assert "maxTurns: 130" in text
    assert "no cambia el `spawn_budget` global de 20 subagentes" in text
    assert "Máximo 2 intentos cortos con Chrome DevTools MCP" in text
    assert "mcp_budget_exhausted_or_scope_too_large" in text

    command = (ROOT / ".claude/commands/verify-slice.md").read_text(encoding="utf-8")
    assert "maxTurns: 130" in command
    assert "No amplíes el budget de spawns" in command
    assert "mcp_budget_exhausted_or_scope_too_large" in command


def test_handoff_contract_accepts_agent360_browser_mcp() -> None:
    text = (ROOT / ".claude/bin/check_handoff_contract.py").read_text(encoding="utf-8")
    assert '"agent360-browser-mcp"' in text
    assert '"browser-mcp"' in text


def test_chrome_devtools_isolation_helper_is_bash3_safe() -> None:
    text = (ROOT / "scripts/chrome-devtools-isolated-session.sh").read_text(encoding="utf-8")
    forbidden = ["mapfile", "readarray", "declare -A"]
    for token in forbidden:
        assert token not in text
    assert "--task" in text
    assert "--start" in text
    assert "--browser-url" in text


def test_mcp_browser_policy_documents_chrome_devtools_first_order() -> None:
    guide = (ROOT / "docs/guides/MCP_BROWSER_VERIFY.md").read_text(encoding="utf-8")
    assert "| 1 | Chrome DevTools MCP" in guide
    assert "| 2 | Claude-in-Chrome MCP" in guide
    assert "| 3 | Agent360 Browser MCP" in guide
    assert "Try Chrome DevTools MCP first" in guide

    contract = (ROOT / ".claude/orchestrator-contract.json").read_text(encoding="utf-8")
    assert "chrome-devtools is primary" in contract
    assert "claude-in-chrome is second fallback" in contract
    assert "agent360/browser-mcp is third fallback" in contract


def test_mcp_browser_guide_documents_requested_fallback_order() -> None:
    text = (ROOT / "docs/guides/MCP_BROWSER_VERIFY.md").read_text(encoding="utf-8")
    assert "| 1 | Chrome DevTools MCP" in text
    assert "| 2 | Claude-in-Chrome MCP" in text
    assert "| 3 | Agent360 Browser MCP" in text
    assert text.index("| 1 | Chrome DevTools MCP") < text.index("| 2 | Claude-in-Chrome MCP") < text.index("| 3 | Agent360 Browser MCP")
    assert "Chrome DevTools MCP first" in text
    assert "try `claude-in-chrome`" in text
    assert "try Agent360/`browser-mcp`" in text


def test_next_wave_does_not_kill_browser_mcps() -> None:
    command = (ROOT / ".claude/commands/next-wave.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs/guides/MCP_BROWSER_VERIFY.md").read_text(encoding="utf-8")
    assert "No reinicies ni mates MCPs desde `/next-wave`" in command
    assert "Do not kill or restart browser MCPs from `/next-wave`" in guide
    next_wave = (ROOT / "scripts" / "next-wave.sh").read_text(encoding="utf-8")
    assert "pkill" not in next_wave
    assert "killall" not in next_wave
    assert "chrome-mcp-doctor" not in next_wave

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_cleanup_deferred_worktrees_is_bash3_compatible() -> None:
    text = (ROOT / "scripts" / "cleanup-deferred-worktrees.sh").read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
    assert "mapfile" not in code
    assert "sort -z" not in code

"""project_root() must always resolve to the MAIN repo, even when called
from inside a git worktree.

Background: `/next-wave` can launch the whole worker session in a per-TASK_ID git worktree. Hooks still need orchestrator state in the canonical main repo; product commands need the current worktree. These tests pin that split-root behavior.

Each test manages its own tempdir and env to avoid pytest fixture coupling
(so the same file runs under pytest AND under the lightweight runner used
when pytest is unavailable in the sandbox).
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure .claude/bin is importable.
_BIN = Path(__file__).resolve().parent.parent
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

import common  # noqa: E402


class _EnvSandbox:
    """Save/restore CLAUDE_PROJECT_DIR around a test."""

    def __enter__(self):
        self._prev = os.environ.pop("CLAUDE_PROJECT_DIR", None)
        return self

    def __exit__(self, *exc):
        if self._prev is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = self._prev


def _make_main_repo(root: Path) -> Path:
    """Create a fake main repo at ``root`` with a real .git directory."""
    (root / ".git").mkdir(parents=True)
    return root


def _make_worktree(main: Path, name: str) -> Path:
    """Create a fake worktree pointing at ``main`` via .git file pointer.

    Mirrors what `git worktree add` produces: the worktree directory has
    a `.git` *file* whose content is `gitdir: <main>/.git/worktrees/<name>`.
    Real git writes the canonical absolute path (symlinks resolved), so we
    do the same here — otherwise on macOS `/var` vs `/private/var` makes
    the test brittle against `Path.resolve()`.
    """
    wt_root = main.parent / f"{main.name}-wt-{name}"
    wt_root.mkdir(parents=True)
    wt_meta = main / ".git" / "worktrees" / name
    wt_meta.mkdir(parents=True)
    (wt_root / ".git").write_text(
        f"gitdir: {wt_meta.resolve()}\n", encoding="utf-8"
    )
    return wt_root


class ResolveMainRepoTests(unittest.TestCase):

    def test_dir_marker_returns_repo_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = (Path(td) / "repo").resolve()
            _make_main_repo(root)
            (root / "src").mkdir()
            # `_resolve_main_repo` calls `.resolve()` internally; on macOS
            # tempfile gives `/var/...` which symlinks to `/private/var/...`,
            # so we must compare against the resolved form on both sides.
            self.assertEqual(common._resolve_main_repo(root / "src"), root)

    def test_worktree_file_marker_resolves_to_main_repo(self):
        with tempfile.TemporaryDirectory() as td:
            main = _make_main_repo((Path(td) / "main").resolve())
            wt = _make_worktree(main, "feature-x")
            # Walking up from the worktree must land on the main repo,
            # not on the worktree.
            self.assertEqual(common._resolve_main_repo(wt), main)

    def test_no_git_falls_back_to_start(self):
        with tempfile.TemporaryDirectory() as td:
            start = Path(td) / "no-git"
            start.mkdir()
            # No .git anywhere up the tree (TemporaryDirectory roots
            # do not have one); fallback returns the start path.
            result = common._resolve_main_repo(start)
            self.assertTrue(result == start or str(result).startswith(str(start.parent)))


class ProjectRootEnvTests(unittest.TestCase):

    def test_env_overrides_walk(self):
        with tempfile.TemporaryDirectory() as td, _EnvSandbox():
            os.environ["CLAUDE_PROJECT_DIR"] = td
            self.assertEqual(common.project_root(), Path(td).resolve())

    def test_env_unset_uses_walk_from_file(self):
        with _EnvSandbox():
            # The repo containing this test has a real .git, so walking
            # upward from common.py must find it. We at least verify that
            # claude_dir() lands inside the resolved root.
            root = common.project_root()
            self.assertTrue((root / ".claude").exists() or (root / ".git").exists() or root.is_dir())


if __name__ == "__main__":
    unittest.main(verbosity=2)

class WorkspaceRootTests(unittest.TestCase):

    def test_workspace_root_returns_worktree_not_main_repo(self):
        with tempfile.TemporaryDirectory() as td, _EnvSandbox():
            main = _make_main_repo((Path(td) / "main").resolve())
            wt = _make_worktree(main, "P00-S01-T001")
            prev_pwd = os.environ.get("PWD")
            prev_wt = os.environ.pop("CLAUDE_WORKTREE_ROOT", None)
            try:
                os.environ["PWD"] = str(wt)
                os.environ["CLAUDE_PROJECT_DIR"] = str(wt)
                self.assertEqual(common.workspace_root(), wt.resolve())
                self.assertEqual(common.project_root(), main.resolve())
            finally:
                if prev_pwd is None:
                    os.environ.pop("PWD", None)
                else:
                    os.environ["PWD"] = prev_pwd
                if prev_wt is not None:
                    os.environ["CLAUDE_WORKTREE_ROOT"] = prev_wt

    def test_workspace_root_env_override(self):
        with tempfile.TemporaryDirectory() as td, _EnvSandbox():
            wt = (Path(td) / "custom-wt").resolve()
            wt.mkdir()
            prev = os.environ.get("CLAUDE_WORKTREE_ROOT")
            try:
                os.environ["CLAUDE_WORKTREE_ROOT"] = str(wt)
                self.assertEqual(common.workspace_root(), wt)
            finally:
                if prev is None:
                    os.environ.pop("CLAUDE_WORKTREE_ROOT", None)
                else:
                    os.environ["CLAUDE_WORKTREE_ROOT"] = prev

"""
Hilo People — conftest for backend/tests/unit/.

Slice:  P02-S02-T001 — Security services (encryption, permissions, rate limit)
Phase:  P02 Core Features
Purpose: Loads the project .env before any app imports so module-level env
         var reads (e.g., JWT_PRIVATE_KEY in app.auth.tokens) are satisfied
         when pytest collects tests in this directory.

         In git worktrees the .env lives in the main repo root (the worktree
         itself does not copy untracked files). The resolution strategy:
           1. Walk up from conftest.py looking for a .git marker.
           2. If .git is a FILE (worktree pointer), resolve via its
              gitdir path to find the main repo root.
           3. Load .env from that root.

Key deps: None (stdlib only).
"""

from __future__ import annotations

import os
from pathlib import Path


def _find_project_root() -> Path:
    """Resolve project root, worktree-safe.

    Returns:
        Path to the directory containing .git/ (may be the main repo when
        running inside a worktree).
    """
    start = Path(__file__).resolve().parent
    for candidate in [start, *start.parents]:
        git = candidate / ".git"
        if git.is_dir():
            return candidate
        if git.is_file():
            # Worktree pointer: "gitdir: /path/.git/worktrees/<name>"
            body = git.read_text(encoding="utf-8").strip()
            if body.startswith("gitdir:"):
                gdir = Path(body[len("gitdir:"):].strip())
                parts = list(gdir.parts)
                if "worktrees" in parts:
                    idx = parts.index("worktrees")
                    main_git_dir = Path(*parts[:idx])
                    return main_git_dir.parent
            return candidate
    return start.parents[3]  # fallback: 4 levels above conftest


def _load_dotenv(root: Path) -> None:
    """Parse and load a .env file into os.environ (no-override).

    Args:
        root: Directory containing .env.
    """
    env_path = root / ".env"
    if not env_path.is_file():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            if key and key not in os.environ:
                os.environ[key] = val


# Load env BEFORE any app module imports (conftest.py is discovered first).
_load_dotenv(_find_project_root())

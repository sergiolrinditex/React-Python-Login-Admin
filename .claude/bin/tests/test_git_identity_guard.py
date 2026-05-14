from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / ".claude" / "bin").mkdir(parents=True)
    (repo / "docs" / "source-of-truth").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "check-git-identity.sh", repo / "scripts" / "check-git-identity.sh")
    shutil.copy2(ROOT / ".claude" / "bin" / "stack_profile.py", repo / ".claude" / "bin" / "stack_profile.py")
    (repo / "scripts" / "check-git-identity.sh").chmod(0o755)
    (repo / "docs" / "source-of-truth" / "STACK_PROFILE.yaml").write_text("profile_version: stack-profile-v1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    return repo


def test_git_identity_guard_passes_with_configured_git_identity(tmp_path):
    repo = make_repo(tmp_path)

    result = subprocess.run(["bash", "scripts/check-git-identity.sh"], cwd=repo, text=True, capture_output=True, check=True)

    assert "GIT_IDENTITY_READY: yes" in result.stdout
    assert "GIT_IDENTITY_USER_NAME: Test User" in result.stdout
    assert "GIT_IDENTITY_USER_EMAIL: test@example.com" in result.stdout


def test_git_identity_guard_blocks_expected_name_mismatch_without_hardcoding(tmp_path):
    repo = make_repo(tmp_path)
    env = {**os.environ, "CLAUDE_EXPECTED_GIT_USER": "expected-user"}

    result = subprocess.run(["bash", "scripts/check-git-identity.sh", "--strict"], cwd=repo, env=env, text=True, capture_output=True)

    assert result.returncode == 3
    assert "GIT_IDENTITY_READY: no" in result.stdout
    assert "expected='expected-user'" in result.stdout
    assert "git config user.name 'expected-user'" in result.stdout


def test_git_identity_guard_reads_expected_identity_from_stack_profile(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "docs" / "source-of-truth" / "STACK_PROFILE.yaml").write_text(
        """
profile_version: stack-profile-v1
git_identity:
  user_name: Test User
  user_email: test@example.com
""".lstrip(),
        encoding="utf-8",
    )

    result = subprocess.run(["bash", "scripts/check-git-identity.sh"], cwd=repo, text=True, capture_output=True, check=True)

    assert "GIT_IDENTITY_READY: yes" in result.stdout
    assert "GIT_IDENTITY_EXPECTATION: enforced" in result.stdout

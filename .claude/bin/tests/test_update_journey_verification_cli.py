from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

import common  # noqa: E402


def _root():
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    (root / "orchestrator-state" / "tasks").mkdir(parents=True)
    (root / "orchestrator-state" / "memory").mkdir(parents=True)
    return root, td


def test_update_journey_verified_under_locks():
    root, td = _root()
    try:
        prev = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(root)
        common._LOCK_DEPTH.clear()
        common.save_registry({"journeys": [{"id": "J001", "verification_status": "pending"}], "tasks": [], "phases": []})
        common.save_runtime_state({"pending_journey_verifications": ["J001"]})
        proc = subprocess.run(
            [sys.executable, "-B", "-S", str(_BIN / "update_journey_verification.py"), "J001", "--outcome", "verified"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)},
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout
        result = json.loads(proc.stdout)
        assert result["ok"] is True
        assert common.load_runtime_state()["pending_journey_verifications"] == []
        assert common.load_registry()["journeys"][0]["verification_status"] == "verified"
    finally:
        if prev is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = prev
        td.cleanup()


def test_update_journey_waiver_requires_reason():
    root, td = _root()
    try:
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
        common._LOCK_DEPTH.clear()
        prev = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(root)
        common.save_registry({"journeys": [{"id": "J001", "verification_status": "pending"}], "tasks": [], "phases": []})
        common.save_runtime_state({"pending_journey_verifications": ["J001"]})
        proc = subprocess.run(
            [sys.executable, "-B", "-S", str(_BIN / "update_journey_verification.py"), "J001", "--outcome", "waived"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        assert proc.returncode == 2
        assert "requires --reason" in proc.stdout
    finally:
        if prev is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = prev
        td.cleanup()

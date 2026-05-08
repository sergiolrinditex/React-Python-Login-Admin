from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class AgentRealityAuditTests(unittest.TestCase):
    def test_agent_reality_audit_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", "-S", "scripts/audit-agent-reality.py"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("AGENT_REALITY_AUDIT: ok", result.stdout)


if __name__ == "__main__":
    unittest.main()

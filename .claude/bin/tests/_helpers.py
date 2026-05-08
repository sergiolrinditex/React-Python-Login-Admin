"""Helpers compartidos por los tests del framework.

Vive aparte de `conftest.py` porque pytest no expone `conftest` como módulo
importable; los helpers compartidos van en su propio fichero al que
`conftest.py` añade el sys.path.
"""
from __future__ import annotations

import json


def make_subagent_stop_payload(agent_type: str, trailer_lines: list[str]) -> str:
    """Devuelve el payload JSON que el SubagentStop hook recibe por stdin."""
    return json.dumps({
        "agent_type": agent_type,
        "last_assistant_message": "\n".join(trailer_lines),
    })

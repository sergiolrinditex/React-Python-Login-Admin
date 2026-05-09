"""
Deterministic demo for /verify-slice human gate — supervisor topic-routing.

Slice: P00-S02-T008 — deepagents Supervisor + topic-routing runtime
Phase: P00 — Scaffold + Design System

Loads the productive verification fixture
(data/verification/mcp_agents/agents.json) into AgentSpec objects, builds a
DeepAgentsSupervisor with the deterministic StubExecutor (no LLM, no DB), and
prints a single routing decision plus the stub subagent output for ONE message
provided as the only positional argument.

Why this exists:
  /verify-slice declares three documented invocations that must produce a
  deterministic routing outcome (hr-policies-agent / langchain-docs-agent /
  fallback). This script is the human-reproducible entry point for that gate.

Design notes:
  - Runs from repo root (`python scripts/demo_supervisor_routing.py "..."`)
    or from `backend/` cwd (`python ../scripts/demo_supervisor_routing.py
    "..."`). Resolves the repo root from `__file__` so cwd does not matter.
  - Stdlib only. No new dependencies. Reuses app.agents.* + app.core.logging.
  - --verbose toggles configure_logging(verbose=True) — default is silent so
    the printed lines are unambiguous for grep / evidence capture.
  - Exit 0 for any of the three documented messages (fallback is a valid
    result, not an error). Non-zero only on argparse error or unexpected
    exception (re-raised after a stderr print).

Dependencies:
  - app.agents.specs.load_specs_from_json
  - app.agents.deepagents_runtime.build_supervisor
  - app.agents._executor.StubExecutor
  - app.agents.routing.select_subagent (for the printed decision metadata)
  - app.core.logging.configure_logging
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap: add backend/ to sys.path so `app.*` imports resolve whether
# we are invoked from repo root or from backend/. Must happen BEFORE importing
# app.*  hence the noqa(E402) markers on the imports below.
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parent.parent  # scripts/ → repo root
_BACKEND_DIR = _REPO_ROOT / "backend"
_FIXTURE_PATH = _REPO_ROOT / "data" / "verification" / "mcp_agents" / "agents.json"

if not _BACKEND_DIR.is_dir():
    print(
        f"[demo_supervisor_routing] backend/ dir not found at {_BACKEND_DIR}",
        file=sys.stderr,
    )
    sys.exit(2)

sys.path.insert(0, str(_BACKEND_DIR))

from app.agents._executor import StubExecutor  # noqa: E402
from app.agents.deepagents_runtime import build_supervisor  # noqa: E402
from app.agents.routing import select_subagent  # noqa: E402
from app.agents.specs import load_specs_from_json  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args: one positional `message` + optional `--verbose`."""
    parser = argparse.ArgumentParser(
        prog="demo_supervisor_routing.py",
        description=(
            "Deterministic supervisor routing demo (P00-S02-T008). "
            "Loads agents.json fixture, builds supervisor with StubExecutor, "
            "prints routing decision + stub output for one user message."
        ),
    )
    parser.add_argument(
        "message",
        type=str,
        help="User message to route (single positional arg; quote it).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose structlog output (configure_logging(verbose=True)).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the demo for a single message and print routing + stub output."""
    args = _parse_args(argv)

    # Honour the project's logging contract: silent by default; verbose on flag.
    configure_logging(verbose=args.verbose)

    if not _FIXTURE_PATH.is_file():
        print(
            f"[demo_supervisor_routing] fixture not found at {_FIXTURE_PATH}",
            file=sys.stderr,
        )
        return 2

    specs = load_specs_from_json(_FIXTURE_PATH)
    supervisor = build_supervisor(specs, executor=StubExecutor())

    # Compute the routing decision separately so we can print its fields.
    # build_supervisor() already filtered subagents internally; reproduce the
    # same filter here for the decision printout (no behaviour change).
    subagents = [s for s in specs if s.agent_type == "subagent"]
    decision = select_subagent(args.message, subagents)
    output = supervisor.invoke(args.message)

    print(
        f"selected_subagent={decision.selected_subagent} "
        f"score={decision.score} "
        f"matched={decision.matched_topics} "
        f"fallback_used={decision.fallback_used}"
    )
    print(output)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover — last-resort guard
        print(
            f"[demo_supervisor_routing] unexpected error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise

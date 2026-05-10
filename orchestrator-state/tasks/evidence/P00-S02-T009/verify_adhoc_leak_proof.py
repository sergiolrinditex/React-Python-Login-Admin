"""Verify-slice adhoc proof for P00-S02-T009 — fresh-process httpx leak check.

Runs OUTSIDE pytest. Exercises the production configure_logging() in a brand-new
Python process and captures stdout+stderr verbatim while making httpx calls with
sentinel URLs that contain Gemini-style ?key=AIza... query strings.

Acceptance:
- A1: verbose=True + URL with ?key=AIza... → stdout/stderr has NO 'AIza' substring
- A3: verbose=False (production) → also silent
- A4: WARNING from httpx still propagates after suppression
- A2: OpenAI Bearer pattern check (defense-in-depth)
"""
from __future__ import annotations

import asyncio
import io
import logging
import re
import sys
from contextlib import redirect_stderr, redirect_stdout

import httpx

# Make backend/ importable
sys.path.insert(0, "backend")

from app.core.logging import configure_logging  # noqa: E402

SENTINEL_AIZA = "AIzaSyFAKE-VERIFY-2026-05-10-DO-NOT-LEAK-T009"
SENTINEL_OPENAI = "sk-FAKEVERIFY1234567890XYZABCDEF1234"
LEAK_PATTERN = re.compile(r"AIza|sk-[A-Za-z0-9]{20}")
HTTP_REQUEST_MARKER = "HTTP Request:"


def _reset_logging_state() -> None:
    """Force re-configure on next call (T009 fix is idempotent inside _configured)."""
    import app.core.logging as logmod

    logmod._configured = False
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    # Reset httpx/httpcore named loggers to NOTSET so we observe the *fix*, not residue
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.NOTSET)


async def _do_httpx_request(url: str) -> None:
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"models": []})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        await client.get(url)


def run_case(label: str, verbose: bool, url: str) -> tuple[str, int]:
    _reset_logging_state()
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        configure_logging(verbose=verbose)
        asyncio.run(_do_httpx_request(url))
    captured = out.getvalue() + err.getvalue()
    matches = LEAK_PATTERN.findall(captured)
    verdict = "PASS" if not matches else "FAIL"
    print(f"\n=== {label} ===")
    print(f"verbose={verbose}")
    print(f"sentinel_url={url}")
    print(f"captured_len={len(captured)}")
    print(f"http_request_marker_present={HTTP_REQUEST_MARKER in captured}")
    print(f"AIza|sk-pattern_matches={len(matches)}")
    print(f"verdict={verdict}")
    if captured.strip():
        print("--- captured begin ---")
        print(captured)
        print("--- captured end ---")
    else:
        print("(captured: EMPTY — no log output)")
    return verdict, len(matches)


def warning_propagation_case() -> tuple[str, int]:
    """A4: WARNING from httpx must still appear after T009 suppression."""
    _reset_logging_state()
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        configure_logging(verbose=True)
        logging.getLogger("httpx").warning("HTTPX TEST WARNING SENTINEL")
    captured = out.getvalue() + err.getvalue()
    has_warning = "HTTPX TEST WARNING SENTINEL" in captured
    has_leak = bool(LEAK_PATTERN.search(captured))
    verdict = "PASS" if (has_warning and not has_leak) else "FAIL"
    print("\n=== A4 — WARNING propagation ===")
    print(f"warning_present={has_warning}")
    print(f"any_leak_signature={has_leak}")
    print(f"verdict={verdict}")
    return verdict, 0 if verdict == "PASS" else 1


def main() -> int:
    overall_fail = 0
    gemini_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models?key={SENTINEL_AIZA}"
    )
    openai_url = (
        f"https://api.openai.com/v1/models?token={SENTINEL_OPENAI}"
    )

    v1, n1 = run_case("A1 — verbose=True / Gemini ?key=AIza...", True, gemini_url)
    v2, n2 = run_case("A3 — verbose=False / Gemini ?key=AIza...", False, gemini_url)
    v3, n3 = run_case(
        "A2 — verbose=True / OpenAI sk- pattern in URL", True, openai_url
    )
    v4, _ = warning_propagation_case()

    print("\n=== SUMMARY ===")
    for label, v, n in [
        ("A1 verbose=True Gemini  ", v1, n1),
        ("A3 verbose=False Gemini ", v2, n2),
        ("A2 verbose=True OpenAI  ", v3, n3),
        ("A4 WARNING propagation  ", v4, 0),
    ]:
        flag = "OK" if v == "PASS" else "FAIL"
        print(f"  [{flag}] {label} matches={n}")
        if v != "PASS":
            overall_fail += 1

    print(f"\nOVERALL: {'PASS — all 4 cases verified' if overall_fail == 0 else f'FAIL — {overall_fail} case(s) failed'}")
    return 0 if overall_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

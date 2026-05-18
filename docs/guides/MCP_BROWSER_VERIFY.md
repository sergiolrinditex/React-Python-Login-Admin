# Browser MCP fallback policy for `/verify-slice`

This guide documents the **strict order** in which a `slice-verifier` (and any
human-real verification of a DAG slice or journey) must select a browser MCP
backend, and how to recover when the primary one is unavailable.

The policy lives in three places that must stay in sync:

- `.claude/orchestrator-contract.json` → `verify_browser_policy` (machine-readable enums).
- `.claude/agents/slice-verifier.md` and `.claude/commands/verify-slice.md` (agent prompts).
- This file (human-readable rationale + recovery playbook).

If any of the three diverge, fix the contract first, then update the agent
prompts, then update this guide.

## Fallback order

Try Chrome DevTools MCP first. If — and only if — it is genuinely unusable
(profile lock, browser binary missing, MCP server crashed and cannot be
restarted from the current shell), fall back in the listed order.

| Order | MCP | Identifier | Use case |
|---|---|---|---|
| 1 | Chrome DevTools MCP | `chrome-devtools` | **Primary**: full devtools surface (network, console, performance, screenshot, full page snapshot, lighthouse). Pair with `scripts/chrome-devtools-isolated-session.sh` to keep the profile out of the user's daily Chrome. |
| 2 | Claude-in-Chrome MCP | `claude-in-chrome` | **Second fallback**: if Chrome DevTools MCP is listed but unusable. Same Chrome process surface but a lighter tool set; acceptable for journey reproductions when devtools fidelity is not strictly required. |
| 3 | Agent360 Browser MCP | `agent360-browser-mcp` / `browser-mcp` | **Third fallback**: separate runtime (`browser-mcp` is the canonical name; `Agent360 Browser MCP` is the marketing name). Use only when both Chrome DevTools MCP and Claude-in-Chrome MCP are unusable. Cookies, console and screenshots are available; network surface is shallower. |

Chrome DevTools MCP first means the `slice-verifier` MUST attempt
`chrome-devtools` and only escalate after `scripts/chrome-mcp-doctor.sh`
reports an unrecoverable error. Do not skip directly to a fallback because
the primary feels slow; that decision must be documented in the handoff with
`MCP_BROWSER: <fallback>` plus the unrecoverable error code.

## Recovery flow when Chrome DevTools MCP is listed-but-unusable

1. Run `scripts/chrome-mcp-doctor.sh` from the canonical repo root. The
   diagnostic returns a stable string per failure (e.g. `profile_lock`,
   `binary_missing`, `mcp_server_no_response`, `port_in_use`).
2. If the doctor returns `profile_lock`, kill *only* the lock file with
   `scripts/chrome-devtools-isolated-session.sh --start` (the script wraps
   the safe path; never `rm -rf` the profile manually). Retry Chrome DevTools
   MCP twice with short attempts; if still unusable, escalate.
3. Escalation #1: try `claude-in-chrome`. The handoff records
   `MCP_BROWSER: claude-in-chrome` and the unrecoverable code from step 1.
4. Escalation #2: try Agent360/`browser-mcp`. The handoff records
   `MCP_BROWSER: agent360-browser-mcp` (the canonical alias; `browser-mcp`
   is also accepted by `check_handoff_contract.py`).
5. If all three are unusable, do not write a partial handoff. Emit
   `VERIFY_OUTCOME: blocked` with reason `mcp_budget_exhausted_or_scope_too_large`
   or the actual MCP failure code and let the main-orchestrator decide whether
   to schedule a manual verification.

`slice-verifier` may use up to `maxTurns: 130` to absorb Chrome DevTools MCP
overhead, but this **does not change the global per-slice spawn budget of 20
subagents** enforced by `hook_spawn_budget.py`. Keep at least one final-write
turn in reserve so the trailer + handoff append survive the budget.

## What `/next-wave` must not do

`/next-wave` is a lightweight scheduler. It opens worker terminals, compacts
agent memory above the threshold, prunes deferred worktree cleanup and prints
copy/paste commands. It must not touch live MCP processes:

- Do not kill or restart browser MCPs from `/next-wave`. Restarting an MCP that
  another verify-slice run is still using will lose its tab/profile state and
  invalidate the in-flight reproduction.
- `scripts/next-wave.sh` must not call `pkill`, `killall`, or
  `chrome-mcp-doctor.sh` directly. MCP health belongs to `/verify-slice` (which
  runs the doctor explicitly inside the `slice-verifier` agent prompt).

If you observe a stale MCP from `/next-wave`, that is a signal that the previous
slice's `slice-verifier` did not close cleanly — open the previous handoff and
either run `/verify-slice` again on that TASK_ID or waive it explicitly with
`VERIFY_WAIVED: <reason>` signed by a human; do not silently reset state.

## Handoff fields

`/verify-slice` writes these fields under the `## verify-slice` section. Names
are normalized by `check_handoff_contract.py`; both the canonical and the
marketing alias are accepted for the third fallback:

- `MCP_BROWSER`: one of `chrome-devtools`, `claude-in-chrome`,
  `agent360-browser-mcp`, `browser-mcp`. The contract canonicalizes
  `browser-mcp`/`browsermcp`/`Agent360 Browser MCP` → `agent360-browser-mcp`.
- `DATA_CONTRACT_ROWS`, `DATA_SETUP`, `PERSISTED_DATA_OBSERVED`, `FLOWS_TESTED`,
  `EVIDENCE`, `VERIFY_OUTCOME`. See `.claude/bin/check_handoff_contract.py` for
  the full schema.

For `VERIFY_OUTCOME: blocked` with MCP-related reasons, prefer one of:

- `mcp_primary_unusable` (chrome-devtools failed all attempts and no fallback)
- `mcp_budget_exhausted_or_scope_too_large` (ran out of `maxTurns`)
- `mcp_data_contract_missing` (real/provided verification data not loaded)

## See also

- `.claude/orchestrator-contract.json` → `verify_browser_policy` (machine
  source of truth).
- `.claude/agents/slice-verifier.md` (full agent prompt with isolation +
  doctor + escalation flow).
- `.claude/commands/verify-slice.md` (operator-facing flow + profile lock
  recovery instructions).
- `scripts/chrome-mcp-doctor.sh` and
  `scripts/chrome-devtools-isolated-session.sh` (the helpers referenced
  above).

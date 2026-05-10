---
name: official-docs-check
description: Verify the current task or phase against official documentation only. Use before planning, implementation, or deployment when APIs or behavior may have changed.
disable-model-invocation: true
context: fork
agent: Explore
allowed-tools: Read Grep ToolSearch WebSearch WebFetch Write mcp__*
---

Verify the current task or phase against official documentation.

## Rules

- Use official vendor docs only, either via official/vendor domains or trusted MCPs that expose versioned docs.
- Prefer versioned docs if the project pins versions.
- Use `ToolSearch` first. Prefer Context7 for library/framework docs (`resolve-library-id` → `get-library-docs`), then vendor-specific MCPs, then WebFetch/WebSearch on official domains as fallback.
- Batch independent checks in one message: if a slice needs auth provider + router + state manager declarados por el stack, launch those independent MCP/WebFetch calls together and synthesize once.
- For Claude Code topics, use `code.claude.com` and its `llms.txt`/docs map, fetching only the specific official pages needed.
- If docs contradict internal documents, do not propose implementation — produce a discrepancy note.

## Deliverable

Write a note in `orchestrator-state/memory/official-doc-notes/<topic>-<YYYY-MM-DD>.md`:

- Official sources (URLs + dates consulted).
- Key findings.
- Incompatibilities with the source-of-truth pack.
- Recommendation for `planner` or `developer`.

If a discrepancy is found → the orchestrator pauses implementation and reconciles the source-of-truth pack before continuing.

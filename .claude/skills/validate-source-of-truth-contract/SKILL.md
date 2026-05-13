---
name: validate-source-of-truth-contract
description: Validate the source-of-truth pack and refresh generated artifacts if needed.
disable-model-invocation: true
allowed-tools: Read Glob Grep Bash
---

Validate the current repository against the source-of-truth contract.

Canonical location: `docs/source-of-truth/`.

Run:

- `python3 -B -S .claude/bin/bootstrap_source_of_truth.py --validate-only`

If valid, summarize:

- documents found,
- strict canonical discovery in `docs/source-of-truth/`,
- prefix consistency,
- number of phases,
- number of generated tasks if artifacts already exist.

If invalid, summarize:

- blocking errors,
- warnings,
- exact files that caused ambiguity.

---
name: deploy-k8s
description: Standard deployment checklist for Kubernetes, Helm, or Rancher-style rollouts.
disable-model-invocation: true
allowed-tools: Read Grep Glob Write Bash WebSearch WebFetch
---

Use this ONLY when deployment is explicitly in scope in the source-of-truth DAG.

## Sequence

1. Read the DAG phase and deployment task.
2. Verify current vendor documentation for the exact deployment commands and flags you intend to use (via `official-docs-researcher` if the last check is >7 days old).
3. Validate image digests, manifests, Helm charts/values.
4. Dry-run first: `kubectl apply --dry-run=server -f ...` or `helm upgrade --dry-run --debug ...`.
5. Apply in a pre-production environment before production if one exists.
6. Verify readiness and liveness probes pass.
7. Verify health endpoints of the service respond 200.
8. Smoke-test the main user flow.
9. Prepare rollback plan (previous image digest, `helm rollback` command, or equivalent) BEFORE applying to production.
10. Apply to production.
11. Monitor logs + metrics for at least 15 minutes after deploy.
12. Write evidence in `orchestrator-state/tasks/evidence/<TASK_ID>/deploy-*` (manifests applied, versions, timings, smoke-test outputs, rollback command ready).

## Never

- Never modify a manifest "just to make it apply".
- Never deploy from a dirty worktree.
- Never skip the dry-run.
- Never skip the rollback plan.

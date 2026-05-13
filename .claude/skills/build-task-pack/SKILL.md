---
name: build-task-pack
description: Standard for refining or consuming a single task pack from the repo-local registry.
user-invocable: false
allowed-tools: Read Grep Glob Write
---

When working on a task pack:

1. Read `orchestrator-state/tasks/registry.json`.
2. Read the per-task pack: `orchestrator-state/tasks/task-packs/<TASK_ID>.md`. In production explicit DAG, this explicit per-task pack is the only task context; there is no global task selector.
3. Confirm:
   - task ID,
   - title,
   - dependencies,
   - acceptance,
   - verification commands,
   - allowed paths,
   - `conflict_groups`,
   - `write_set`,
   - UX journey fields when UI is touched,
   - Verification Data Contract rows when the slice is verified via UI/API/journey.
4. If `allowed_paths` or `write_set` is empty, refine it from the repo structure before coding whenever possible. If Verification Data Contract rows are missing for a productive UI/API verify, flag the pack as incomplete instead of inventing fake data.
5. If the task is too broad, **do not split it at runtime**. Block and ask the user to update the source-of-truth Coverage Registry with smaller canonical `Slice ID`s, rerun `bootstrap_source_of_truth.py --refresh`, and then continue. Runtime-only sub-slices corrupt DAG adjacency, handoffs, memory and journeys.
6. The pack path must match the current `TASK_ID`. If prompt TASK_ID, pack TASK_ID and handoff TASK_ID differ, stop before editing.
7. In DAG mode, do not broaden `write_set` silently during implementation. If the slice must touch a shared file not declared in the pack, update the handoff with `WRITE_SET_DRIFT:` and ask whether the source-of-truth Coverage Registry should be corrected before continuing.

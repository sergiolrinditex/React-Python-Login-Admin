# Framework tests

Tests del propio framework `.claude/bin/`. **No son tests de las apps que el framework construye**: validan hooks, helpers, bootstrap, locks, reglas estáticas y guards.

## Qué cubren

| Archivo | Cubre |
|---------|-------|
| `test_bootstrap_registry_driven.py` | bootstrap de fases, tasks, coverage registries, BASELINE real, granularidad sintética. |
| `test_bootstrap_journey_matrix.py` | parsing de Journey Coverage Matrix, escapes `\|`, rangos, step/phase refs. |
| `test_design_tokens_guard.py` | guard de design tokens evitando falsos positivos en strings/comentarios. |
| `test_file_lock.py` | locks reentrantes, escritura atómica, serialización inter-proceso. |
| `test_project_root_worktree.py` | resolución del repo principal desde worktrees. |
| `test_spawn_budget.py` | budget mecánico de 20 spawns y visibilidad en SessionStart. |
| `test_static_contracts.py` | settings, carga explícita de rules, memoria externa a `.claude`, spawn=20. |
| `test_subagent_stop_atomicity.py` | `registry.json` + `runtime-state.json` actualizados de forma consistente. |
| `test_trailer_strict.py` | `CLAUDE_TRAILER` estricto y logging visible si falta información. |

## Cómo correrlos

Desde la raíz del repo:

```bash
python3 -B -S -m unittest discover -s .claude/bin/tests
```

Usamos `-B` para no crear `__pycache__` dentro de `.claude/`, y `-S` para evitar contaminación de site-packages. El suite actual no requiere pytest.

## Requisitos

- Python 3.10+.
- POSIX (`fcntl`) para lock real. En Windows el lock degrada a no-op.

## Aislamiento

Cada test que muta estado usa un repo temporal mediante `CLAUDE_PROJECT_DIR` y escribe en `orchestrator-state/`, no en `.claude/`.

"""
Hilo People — Graphs feature package.

Slice:  P02-S08-T001 — Agents endpoints and DeepAgents/LangGraph smoke
Phase:  P02 Core Features
Purpose: Contains LangGraph workflow definitions and Postgres checkpointer
         wiring for the Hilo People agent runtime.

         Contents:
           - workflows.py    — minimal LangGraph workflow stub for smoke test;
                               full approval workflows deferred to future slices.
           - checkpointer.py — Postgres checkpointer wiring stub; concrete
                               setup deferred (no migration in this slice per §J R-2).

Source refs:
  - task pack P02-S08-T001 §D.2, §C.6, §J R-2
  - TECHNICAL_GUIDE §10.4 (graphs/workflows.py + graphs/checkpointer.py)
"""

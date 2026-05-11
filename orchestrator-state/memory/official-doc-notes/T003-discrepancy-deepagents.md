# Official Doc Note: DISCREPANCY — deepagents Beta Status + Forced Provider SDKs

DATE: 2026-05-11
TASK_ID: P00-S01-T003
TOPIC: deepagents package stability and mandatory peer dependencies
SEVERITY: medium
SOURCE: PyPI live JSON https://pypi.org/pypi/deepagents/0.5.9/json

---

## DISCREPANCY DESCRIPTION

### 1. Beta development status

- `deepagents==0.5.9` carries the classifier `Development Status :: 4 - Beta`.
- The task pack §11.2 (paquetes prohibidos) includes "librerías abandonadas" — deepagents is NOT abandoned (maintained by LangChain org, MIT license, active releases).
- However, Beta status means the API may change without a major version bump.
- The source-of-truth (`instrucciones.md §11.0`) lists `deepagents` as `USAR`, so this is an accepted dependency. The Beta flag is a **risk note**, not a blocker per se.

### 2. Mandatory provider-specific peer dependencies

`deepagents==0.5.9` requires (hard deps, not optional):
- `langchain-anthropic>=1.4.3,<2.0.0` — Anthropic provider SDK
- `langchain-google-genai>=4.2.2,<5.0.0` — Google AI provider SDK
- `langsmith>=0.8.0` — LangSmith observability

These are **provider SDKs**, each potentially requiring API keys (ANTHROPIC_API_KEY, GOOGLE_API_KEY, LANGSMITH_API_KEY) at runtime. They do NOT require keys at **import time** — the smoke test (`import deepagents`) will succeed without credentials.

Install footprint impact:
- `langchain-anthropic` pulls `anthropic>=0.50.0` SDK
- `langchain-google-genai` pulls `google-generativeai` + `google-ai-generativelanguage`
- These add ~15-20 transitive packages

### 3. No explicit langgraph pin in deepagents

- `deepagents` does NOT pin `langgraph` in its `requires_dist`.
- It pulls `langchain>=1.2.17` which transitively requires `langgraph` compatibility.
- The chosen versions (`langchain==1.2.18`, `langgraph==1.1.10`) are compatible because deepagents allows `langchain<2.0.0,>=1.2.17` and langgraph 1.1.10 is stable.

---

## IMPACT ON T003

| Impact | Severity | Decision needed |
|---|---|---|
| Beta API stability | Low | Accepted per §11.0 (`USAR`). Document in handoff. |
| Forced provider SDKs (anthropic + google-genai) | Medium | Install proceeds. Smoke test (import only) works without API keys. Keys needed in P01+ auth/AI slices. |
| Install size (+15-20 transitive packages) | Low | Acceptable for production project. |
| langgraph version compatibility | None | Verified compatible — no conflict. |

---

## RECOMMENDATION FOR DEVELOPER

1. Declare `deepagents==0.5.9` in `[project.dependencies]` as planned.
2. The install will pull `langchain-anthropic`, `langchain-google-genai`, `langsmith` automatically.
3. Smoke test: `import deepagents` — will succeed without any API keys.
4. Document in handoff that deepagents is Beta and brings provider SDK transitive deps.
5. ANTHROPIC_API_KEY + GOOGLE_API_KEY are runtime requirements (not install-time) — they belong in `.env` starting from the AI/chat feature slices, not T003.
6. Do NOT add `langchain-anthropic` or `langchain-google-genai` separately to pyproject.toml — they are transitive through deepagents.

---

## HUMAN DECISION REQUIRED?

No blocking decision required for T003. The source-of-truth already lists `deepagents` as `USAR`. The Beta status and provider dep footprint are documented risks, not blockers.

However, if the human wishes to defer deepagents to a later AI feature slice and keep T003's install lighter, that is a valid product decision. In that case, open a follow-up with `scope_classification=scope_expansion` to move deepagents to its own task.

RESOLVED: yes — Developer read this note on 2026-05-11. deepagents==0.5.9 included per §11.0 `USAR` directive. Beta status documented in handoff. Provider SDK transitive deps (langchain-anthropic, langchain-google-genai, langsmith) install cleanly. Smoke test passes (import deepagents with no API keys needed). No human deferral requested since source-of-truth explicitly lists deepagents as USAR.

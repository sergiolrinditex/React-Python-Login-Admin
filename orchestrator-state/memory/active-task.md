# Active task

- ID: P00-S01-T003
- Title: Backend dependency pack
- Status: ready
- Phase: P00

## Acceptance
- FastAPI, SQLAlchemy, Celery, LiteLLM, LangChain, LangGraph, DeepAgents, pgvector deps declared

## Allowed paths
- backend/pyproject.toml
- backend/requirements*.txt
- backend/app/core/**

## DAG conflict guardrails
### Conflict groups
- dependency:backend
### Write set
- backend/pyproject.toml
- backend/requirements*.txt
- backend/app/core/**

## Verification commands
- `pytest backend/tests -k dependency_smoke`

# Active task

- ID: P00-S02-T008
- Title: deepagents Supervisor + topic-routing runtime
- Status: blocked
- Phase: P00

## Acceptance
- agents/deepagents_runtime.py implemented
- supervisor routes user messages to subagents based on subagent_topics overlap

## Allowed paths

## DAG conflict guardrails
### Conflict groups
- agents_runtime
### Write set
- backend/app/agents/**

## Verification commands
- `real flow: user asks vacaciones question -> supervisor routes to hr-policies-agent -> returns answer`
- `user asks langchain question -> routes to langchain-docs-agent`

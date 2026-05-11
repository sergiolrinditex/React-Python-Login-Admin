# Active task

- ID: P01-S01-T001
- Title: 0001_auth_users_employee_audit.py
- Status: ready
- Phase: P01

## Acceptance
- Migration creates auth/profile/audit tables with constraints and rollback

## Allowed paths
- backend/alembic/versions/0001_auth_users_employee_audit.py
- backend/app/db/models/user.py
- backend/app/db/models/auth.py

## DAG conflict guardrails
### Conflict groups
- db:migrations
### Write set
- backend/alembic/versions/0001_auth_users_employee_audit.py
- backend/app/db/models/user.py
- backend/app/db/models/auth.py

## Verification commands
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`

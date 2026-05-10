"""
Feature module: auth — authentication endpoints.

Slice: P01-S02-T001 — POST /api/v1/auth/sign-up
Phase: P01 — Auth + Base Capabilities

Sub-modules:
  - errors.py      — typed domain errors for the auth feature
  - schemas.py     — Pydantic v2 request/response schemas
  - repository.py  — async DB write operations (users, employee_profiles, audit_logs)
  - service.py     — SignUpUserUseCase orchestration
  - routes.py      — FastAPI APIRouter wired in main.py

Dependencies:
  - app.db.models.user (User, EmployeeProfile)
  - app.db.models.auth (AuditLog)
  - app.core.db (get_session)
  - app.core.logging (get_logger)
  - app.core.config (get_settings → corporate_email_domains)
  - argon2-cffi 25.1.0
"""

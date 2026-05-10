"""audit_logs: add ip, user_agent, request_id, resource columns.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-10

Slice: P01-S01-T005 — audit_logs compliance columns (GDPR / non-negotiable audit)
Phase: P01 — Auth + base capabilities

Columns added to audit_logs (ALL nullable=True — backward-compatible with rows
written before this migration was applied, including any existing admin_ai audit entries):

  - ip          INET     — client IP address captured from X-Request-ID middleware
                           via `request.client.host`. PG native type; no extension needed.
  - user_agent  TEXT     — HTTP User-Agent header value (`request.headers.get("user-agent")`).
  - request_id  TEXT     — correlation ID from X-Request-ID middleware
                           (structlog contextvar bound by main.py:77-117).
  - resource    TEXT     — free-form REST-style path/identifier for the affected resource
                           (e.g. "POST /api/v1/auth/sign-up", "users:42"). Semantically
                           distinct from entity_type (which is the DB table name).
                           See §"Naming reconciliation" in task-pack P01-S01-T005.

Why nullable (not NOT NULL):
  - Any audit_log row written by admin_ai/repository.py today (before this migration)
    will have NULL in these 4 columns after upgrade. Making them NOT NULL would require
    backfilling, which is out of scope for a non-destructive schema migration.
  - Population of these columns by auth service endpoints is deferred to P01-S02-T001
    (sign-up = first endpoint that writes audit_logs in the normal auth path).
    See §"Waiver acotado" pre-approved 2026-05-10.

Waiver clause (pre-approved by human 2026-05-10):
  The acceptance clause "auth service populates [columns] on every sensitive action
  via X-Request-ID middleware + request.client + request.headers['User-Agent']" is
  deferred to P01-S02-T001 because no auth endpoint writing audit_logs exists today.
  Reference: runtime-followup#FU-20260509105319, which explicitly anticipated
  "not before P01-S02".

Non-negotiables reference:
  01-non-negotiables.md §Audit log (GDPR / compliance):
    "audit_log(id, user_id, action, resource, timestamp, ip, user_agent,
     metadata_jsonb, request_id)"
  01-non-negotiables.md §Request correlation:
    "request_id viaja en TODOS los logs"

Downgrade discipline:
  drop_column in reverse order (resource, request_id, user_agent, ip).
  The audit_logs table itself is NOT dropped (belongs to migration 0001).

Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3
        task-pack P01-S01-T005 §Front→Back→DB contract
        runtime-followup#FU-20260509105319
"""
from __future__ import annotations

import logging

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "0002"
down_revision: str = "0001"
branch_labels = None
depends_on = None

_log = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    """Add 4 nullable compliance columns to audit_logs.

    BEFORE: audit_logs has 6 columns from migration 0001:
      id, actor_user_id, action, entity_type, entity_id, metadata, created_at

    AFTER: 4 nullable columns appended:
      ip (INET), user_agent (TEXT), request_id (TEXT), resource (TEXT)

    All columns nullable=True, no server_default — pre-existing rows get NULL.
    No indexes added in this migration (no consumer yet; index after audit_logs
    querying lands in P02-S02-T001+). See R1 risk note in task-pack.
    """
    _log.info(
        "P01-S01-T005 upgrade: adding 4 nullable compliance columns to audit_logs"
    )

    # ip — INET (PG native type, no extension needed)
    op.add_column(
        "audit_logs",
        sa.Column(
            "ip",
            INET(),
            nullable=True,
            comment="Client IP address from request.client.host; NULL for pre-middleware rows.",
        ),
    )

    # user_agent — HTTP User-Agent header value
    op.add_column(
        "audit_logs",
        sa.Column(
            "user_agent",
            sa.Text(),
            nullable=True,
            comment="HTTP User-Agent header; NULL for pre-middleware rows.",
        ),
    )

    # request_id — X-Request-ID correlation ID
    op.add_column(
        "audit_logs",
        sa.Column(
            "request_id",
            sa.Text(),
            nullable=True,
            comment=(
                "X-Request-ID correlation ID from structlog contextvar "
                "(main.py:77-117); NULL for pre-middleware rows."
            ),
        ),
    )

    # resource — free-form REST-style resource identifier
    op.add_column(
        "audit_logs",
        sa.Column(
            "resource",
            sa.Text(),
            nullable=True,
            comment=(
                "Free-form REST resource path (e.g. 'POST /api/v1/auth/sign-up'). "
                "Distinct from entity_type (DB table name)."
            ),
        ),
    )

    _log.info(
        "P01-S01-T005 upgrade: completed — audit_logs now has ip, user_agent, "
        "request_id, resource columns (all nullable)"
    )


def downgrade() -> None:
    """Remove the 4 compliance columns from audit_logs in reverse order.

    BEFORE (0002 state): audit_logs has 10 columns.
    AFTER  (0001 state): audit_logs has 6 columns (4 new ones dropped).

    Existing audit_log rows are preserved; only the column definitions are dropped.
    Pre-existing rows return to 0001 shape with their original 6 column values intact.
    """
    _log.info(
        "P01-S01-T005 downgrade: removing 4 compliance columns from audit_logs "
        "(resource, request_id, user_agent, ip)"
    )

    # Drop in reverse order of creation
    op.drop_column("audit_logs", "resource")
    op.drop_column("audit_logs", "request_id")
    op.drop_column("audit_logs", "user_agent")
    op.drop_column("audit_logs", "ip")

    _log.info(
        "P01-S01-T005 downgrade: completed — audit_logs back to 0001 shape (6 columns)"
    )

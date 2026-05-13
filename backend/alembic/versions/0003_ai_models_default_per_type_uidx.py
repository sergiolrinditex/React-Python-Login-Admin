"""0003 — ai_models partial unique index: at-most-one is_default per model_type.

Slice:  P02-S05-T003 — Add partial unique index for is_default=true per model_type in ai_models
Phase:  P02 Core Features
Purpose: Promotes the D-DEF1 invariant ("at most one default model per model_type")
         from application-layer enforcement to DB-level enforcement via a partial
         unique index on ai_models(model_type) WHERE is_default = true.

Reversibility:
    upgrade():   CREATE UNIQUE INDEX ... WHERE is_default = true
    downgrade(): DROP INDEX ai_models_default_per_type_uidx

Assumption:
    The upgrade assumes the database is either empty or already satisfies D-DEF1
    (i.e., no two rows in ai_models share model_type AND is_default = true).
    Verification fixtures (data/verification/admin_ai/providers/litellm_verification.json)
    do NOT seed ai_models rows, so the index will be created cleanly on a fresh DB.
    If manual exploratory data was inserted that violates D-DEF1, the CREATE INDEX will
    fail with a unique_violation. Recovery: identify and remove duplicate defaults with:
        SELECT model_type, array_agg(id) FROM ai_models
        WHERE is_default = true GROUP BY model_type HAVING count(*) > 1;
    Then delete duplicates manually (keep one per model_type) and re-run upgrade.

Source refs:
    - task pack P02-S05-T003 §A (migration 0003 spec)
    - 01-non-negotiables.md §Security: partial unique index pattern for at-most-one invariant
    - instrucciones.md §3.1#admin-ai rule 3
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger("alembic.migration.0003")

# Alembic migration metadata
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add partial unique index ai_models_default_per_type_uidx.

    Enforces D-DEF1 at the DB level: at most one ai_models row per model_type
    may have is_default = true. The index is a PARTIAL unique index (covers only
    rows where is_default = true), which keeps the single-row key small and does
    not affect rows with is_default = false.

    The existing app-layer enforcement in apply_patch() (service.py) clears the
    previous default before setting a new one within the same transaction, which
    keeps the invariant satisfied even inside a single tx (Postgres evaluates
    the partial unique constraint at commit time — not at every DML statement —
    so the interim state where both old and new rows are temporarily true is
    allowed within a transaction, as long as the clearing UPDATE executes before
    the target row is set to true, which is what apply_patch() guarantees).

    The partial unique index provides the additional protection that two concurrent
    transactions both trying to set is_default = true on different rows of the same
    model_type will have exactly one succeed and the other receive IntegrityError
    (UniqueViolation), which the service layer translates to ModelDefaultConflictError
    and the router maps to HTTP 409 AI_MODEL_DEFAULT_CONFLICT.
    """
    logger.info("0003.upgrade: creating index ai_models_default_per_type_uidx")
    op.create_index(
        "ai_models_default_per_type_uidx",
        "ai_models",
        ["model_type"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )
    logger.info(
        "0003.upgrade: index ai_models_default_per_type_uidx created successfully "
        "(UNIQUE ON ai_models(model_type) WHERE is_default = true)"
    )


def downgrade() -> None:
    """Drop the partial unique index ai_models_default_per_type_uidx.

    After downgrade, D-DEF1 enforcement reverts to application-layer only.
    Concurrent race conditions can again result in two defaults per model_type
    until the migration is re-applied.
    """
    logger.info("0003.downgrade: dropping index ai_models_default_per_type_uidx")
    op.drop_index("ai_models_default_per_type_uidx", table_name="ai_models")
    logger.info("0003.downgrade: dropped index ai_models_default_per_type_uidx")

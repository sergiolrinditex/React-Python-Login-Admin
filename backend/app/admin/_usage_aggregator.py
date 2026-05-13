"""
Hilo People — Admin usage aggregation SQL helper.

WRITE_SET_DRIFT §D-USAGE-SPLIT (P02-S05-T002): Split off from admin/usage.py
because that file exceeded 300 LoC. This private module contains the
_aggregate_usage() function that executes the GROUP BY query over
llm_usage_logs. admin/usage.py keeps only the HTTP handler and validation.

Slice:  P02-S05-T002 — Model test and usage endpoints
Phase:  P02 Core Features
Purpose: SQL aggregation over llm_usage_logs LEFT JOIN ai_models + ai_providers,
         grouped by model, day, or model+day. Supports optional model_id and
         provider_id filters.

Key deps:
  - sqlalchemy (select, func, literal)
  - app.db.models.admin_ai (LlmUsageLog, AiModel, AiProvider)

Source refs:
  - task pack P02-S05-T002 §D.2.B (query shape, group_by values)
  - task pack P02-S05-T002 §D.4 §D-USAGE-SPLIT (conditional split >300 LoC)
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models.admin_ai import AiModel, AiProvider, LlmUsageLog

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def aggregate_usage(
    session: Session,
    *,
    from_utc: datetime,
    to_utc: datetime,
    group_by: str,
    model_id: uuid.UUID | None,
    provider_id: uuid.UUID | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Execute the usage aggregation query and return rows + totals.

    Performs a SELECT over llm_usage_logs LEFT JOIN ai_models LEFT JOIN ai_providers,
    grouped by the requested dimension. Applies optional model_id + provider_id filters.

    Args:
        session:     Active SQLAlchemy sync Session.
        from_utc:    Window start (inclusive, UTC).
        to_utc:      Window end (exclusive, UTC).
        group_by:    'model' | 'day' | 'model_day'.
        model_id:    Optional model UUID filter.
        provider_id: Optional provider UUID filter (via ai_models.provider_id).

    Returns:
        Tuple (rows, totals):
          - rows: list of row dicts (fields depend on group_by).
          - totals: summary dict (tokens_in, tokens_out, estimated_cost,
                    invocations, latency_ms_avg).
    """
    if _VERBOSE:
        logger.debug(
            "admin._usage_aggregator.start from=%s to=%s group_by=%s",
            from_utc.isoformat(), to_utc.isoformat(), group_by,
        )  # BEFORE

    conditions = [
        LlmUsageLog.created_at >= from_utc,
        LlmUsageLog.created_at < to_utc,
    ]
    if model_id is not None:
        conditions.append(LlmUsageLog.model_id == model_id)
    if provider_id is not None:
        conditions.append(AiModel.provider_id == provider_id)

    agg_cols: list[Any] = [
        sa.func.sum(LlmUsageLog.tokens_in).label("tokens_in"),
        sa.func.sum(LlmUsageLog.tokens_out).label("tokens_out"),
        sa.func.sum(LlmUsageLog.estimated_cost).label("estimated_cost"),
        sa.func.avg(LlmUsageLog.latency_ms).label("latency_ms_avg"),
        sa.func.count(LlmUsageLog.id).label("invocations"),
    ]
    group_cols: list[Any] = []

    if group_by in ("model", "model_day"):
        agg_cols = [
            LlmUsageLog.model_id.label("model_id"),
            AiModel.model_id.label("model_name"),
            AiProvider.provider_type.label("provider_type"),
        ] + agg_cols
        group_cols = [LlmUsageLog.model_id, AiModel.model_id, AiProvider.provider_type]

    if group_by in ("day", "model_day"):
        day_expr = sa.func.date_trunc(sa.literal("day"), LlmUsageLog.created_at)
        agg_cols.append(day_expr.label("day"))
        group_cols.append(day_expr)

    stmt = (
        sa.select(*agg_cols)
        .select_from(LlmUsageLog)
        .outerjoin(AiModel, LlmUsageLog.model_id == AiModel.id)
        .outerjoin(AiProvider, AiModel.provider_id == AiProvider.id)
        .where(*conditions)
    )
    if group_cols:
        stmt = stmt.group_by(*group_cols)

    if group_by == "day":
        stmt = stmt.order_by(sa.text("day ASC"))
    elif group_by == "model":
        stmt = stmt.order_by(sa.text("model_name ASC"))
    elif group_by == "model_day":
        stmt = stmt.order_by(sa.text("model_name ASC, day ASC"))

    db_rows = session.execute(stmt).mappings().all()

    rows: list[dict[str, Any]] = []
    tot_ti = tot_to = tot_inv = 0
    tot_cost = 0.0
    lat_sum = 0.0
    lat_count = 0

    for row in db_rows:
        rd: dict[str, Any] = {
            "tokens_in": int(row["tokens_in"] or 0),
            "tokens_out": int(row["tokens_out"] or 0),
            "estimated_cost": float(row["estimated_cost"] or 0.0),
            "latency_ms_avg": int(row["latency_ms_avg"]) if row["latency_ms_avg"] else None,
            "invocations": int(row["invocations"] or 0),
        }
        if group_by in ("model", "model_day"):
            rd["model_id"] = str(row["model_id"]) if row["model_id"] else None
            rd["model_name"] = row["model_name"]
            rd["provider_type"] = row["provider_type"]
        if group_by in ("day", "model_day"):
            dv = row["day"]
            rd["day"] = dv.date().isoformat() if dv else None
        rows.append(rd)
        tot_ti += rd["tokens_in"]
        tot_to += rd["tokens_out"]
        tot_cost += rd["estimated_cost"]
        tot_inv += rd["invocations"]
        if rd["latency_ms_avg"] is not None:
            lat_sum += rd["latency_ms_avg"] * rd["invocations"]
            lat_count += rd["invocations"]

    totals: dict[str, Any] = {
        "tokens_in": tot_ti,
        "tokens_out": tot_to,
        "estimated_cost": round(tot_cost, 8),
        "invocations": tot_inv,
        "latency_ms_avg": int(lat_sum / lat_count) if lat_count else None,
    }

    if _VERBOSE:
        logger.debug(
            "admin._usage_aggregator.ok rows=%d invocations=%d",
            len(rows), tot_inv,
        )  # AFTER
    return rows, totals

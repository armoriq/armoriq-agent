"""
Dashboard product metrics routes.

GET /dashboard/products/{product}/summary
GET /dashboard/products/{product}/recent-activity
GET /dashboard/products/{product}/timeseries
"""
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Query
from sqlalchemy import case, func, select

from app.api.deps import DbSession
from app.models.database import ApiKey, AuditLog, IntentPlan

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Token pricing — claude-sonnet-4-6
_PRICE_INPUT = 3.00
_PRICE_OUTPUT = 15.00

ProductName = Literal["armorclaude", "armorcodex", "armorcopilot"]
WindowName = Literal["7d", "30d", "90d"]


def _window_days(w: str) -> int:
    return {"7d": 7, "90d": 90}.get(w, 30)


def _since(days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=days)


def _empty_summary(product: str, window: str) -> dict:
    return {
        "product": product,
        "window": window,
        "deviceApprovals": {"value": 0, "deltaPct": 0},
        "activeApiKeys": {"value": 0},
        "intentPlans": {"value": 0, "deltaPct": 0},
        "auditEvents": {"value": 0, "deltaPct": 0},
        "allowRate": 100,
        "tokensConsumed": {
            "input": 0, "output": 0, "total": 0,
            "estimatedSpendUsd": 0.0,
            "byModel": {
                "claude-sonnet-4-6": {"input": 0, "output": 0},
                "claude-haiku-4-5":  {"input": 0, "output": 0},
            },
        },
    }


@router.get("/products/{product}/summary")
async def product_summary(
    product: ProductName,
    db: DbSession,
    window: WindowName = Query("30d"),
):
    days = _window_days(window)
    since = _since(days)

    # Aggregate from audit_logs filtered by product
    logs_result = await db.execute(
        select(
            func.count().label("total"),
            func.sum(
                case((AuditLog.status == "success", 1), else_=0)
            ).label("allowed"),
            func.sum(AuditLog.tokens_input).label("tokens_in"),
            func.sum(AuditLog.tokens_output).label("tokens_out"),
        ).where(AuditLog.executed_at >= since, AuditLog.product == product)
    )
    row = logs_result.one()
    total = row.total or 0
    allowed = int(row.allowed or 0)
    tokens_in = int(row.tokens_in or 0)
    tokens_out = int(row.tokens_out or 0)
    allow_rate = round((allowed / total) * 100) if total > 0 else 100

    # Distinct plans in window
    plans_result = await db.execute(
        select(func.count(func.distinct(AuditLog.intent_plan_id))).where(
            AuditLog.executed_at >= since,
            AuditLog.product == product,
            AuditLog.intent_plan_id.isnot(None),
        )
    )
    plan_count = plans_result.scalar() or 0

    # Active API keys (used in last 10 min)
    active_cutoff = datetime.utcnow() - timedelta(minutes=10)
    active_keys_result = await db.execute(
        select(func.count()).where(ApiKey.last_used_at >= active_cutoff, ApiKey.status == "active")
    )
    active_keys = active_keys_result.scalar() or 0

    total_tokens = tokens_in + tokens_out
    spend = (tokens_in / 1_000_000) * _PRICE_INPUT + (tokens_out / 1_000_000) * _PRICE_OUTPUT

    # Model breakdown labels differ per product
    if product == "armorcodex":
        by_model = {
            "o4-mini": {"input": round(tokens_in * 0.6), "output": round(tokens_out * 0.6)},
            "o3":      {"input": round(tokens_in * 0.4), "output": round(tokens_out * 0.4)},
        }
    elif product == "armorcopilot":
        by_model = {
            "copilot-gpt-4o":    {"input": round(tokens_in * 0.7), "output": round(tokens_out * 0.7)},
            "copilot-gpt-4o-mini": {"input": round(tokens_in * 0.3), "output": round(tokens_out * 0.3)},
        }
    else:
        by_model = {
            "claude-sonnet-4-6": {"input": round(tokens_in * 0.7), "output": round(tokens_out * 0.7)},
            "claude-haiku-4-5":  {"input": round(tokens_in * 0.3), "output": round(tokens_out * 0.3)},
        }

    return {
        "product": product,
        "window": window,
        "deviceApprovals": {"value": 0, "deltaPct": 0},
        "activeApiKeys": {"value": active_keys},
        "intentPlans": {"value": plan_count, "deltaPct": 0},
        "auditEvents": {"value": total, "deltaPct": 0},
        "allowRate": allow_rate,
        "tokensConsumed": {
            "input": tokens_in,
            "output": tokens_out,
            "total": total_tokens,
            "estimatedSpendUsd": round(spend, 6),
            "byModel": by_model,
        },
    }


@router.get("/products/{product}/recent-activity")
async def product_recent_activity(
    product: ProductName,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
):
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.product == product)
        .order_by(AuditLog.executed_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    return [
        {
            "id": str(log.id),
            "action": log.action,
            "tool": log.tool,
            "status": log.status,
            "executedAt": log.executed_at.isoformat(),
            "agentId": None,
            "sessionId": log.session_id,
        }
        for log in logs
    ]


@router.get("/products/{product}/timeseries")
async def product_timeseries(
    product: ProductName,
    db: DbSession,
    window: WindowName = Query("30d"),
):
    days = _window_days(window)
    since = _since(days)

    result = await db.execute(
        select(
            func.date_trunc("day", AuditLog.executed_at).label("day"),
            func.count().label("total"),
            func.sum(
                case((AuditLog.status == "success", 1), else_=0)
            ).label("allowed"),
        )
        .where(AuditLog.executed_at >= since, AuditLog.product == product)
        .group_by("day")
        .order_by("day")
    )

    return [
        {
            "date": row.day.strftime("%Y-%m-%d"),
            "allowed": int(row.allowed or 0),
            "denied": int(row.total or 0) - int(row.allowed or 0),
        }
        for row in result.all()
    ]

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status

from services.auth import OrgContext
from services.supabase_client import db, ScopedSupabaseClient
from services.usage import get_current_usage


LIMIT_METRIC_TABLES = {
    "users": "organization_users",
    "leads": "leads",
    "products": "products",
}


def get_subscription(organization_id: str) -> dict | None:
    rows = ScopedSupabaseClient(db, organization_id).select("subscriptions", limit=1)
    return rows[0] if rows else None


def get_plan_limit(plan_id: str, metric: str, period: str = "none") -> Optional[int]:
    rows = db.select(
        "plan_limits",
        filters={"plan_id": f"eq.{plan_id}", "metric": f"eq.{metric}", "period": f"eq.{period}"},
        select_cols="limit_value",
        limit=1,
    )
    if not rows:
        return None
    value = rows[0].get("limit_value")
    return int(value) if value is not None else None


def get_month_start_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def get_usage_for_limit(org: OrgContext, metric: str, period: str) -> int:
    if period == "monthly":
        return get_current_usage(org.organization_id, metric, since_iso=get_month_start_iso())
    if metric in LIMIT_METRIC_TABLES:
        return org.db.count(LIMIT_METRIC_TABLES[metric])
    return get_current_usage(org.organization_id, metric)


def assert_plan_allows(org: OrgContext, metric: str, quantity: int = 1, period: str = "none") -> None:
    """Raise 402 if org exceeds plan limit. -1 means explicitly unlimited.

    A *missing* plan_limits row (unconfigured plan/metric/period combo) is
    NOT treated the same as -1 — it fails closed instead of silently
    granting unlimited usage, so a misconfigured/forgotten plan_limits seed
    blocks the action (a clear, fixable error) rather than quietly giving
    away free usage.
    """
    subscription = get_subscription(org.organization_id)
    plan_id = (subscription or {}).get("plan_id") or "starter"
    limit = get_plan_limit(plan_id, metric, period)
    if limit is not None and limit < 0:
        return

    if limit is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "plan_limit_not_configured",
                "metric": metric,
                "plan": plan_id,
            },
        )

    current = get_usage_for_limit(org, metric, period)
    if current + quantity > limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "plan_limit_exceeded",
                "metric": metric,
                "plan": plan_id,
                "limit": limit,
                "current": current,
                "requested": quantity,
            },
        )

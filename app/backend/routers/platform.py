from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from services.platform_auth import PlatformAdminContext, require_platform_role
from services.supabase_client import db

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/summary")
def platform_summary(admin: PlatformAdminContext = Depends(require_platform_role())):
    orgs = db.select("organizations", limit=10000)
    subscriptions = db.select("subscriptions", limit=10000)
    usage_30d_since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    usage = db.select_all("usage_events", filters={"created_at": f"gte.{usage_30d_since}"}, select_cols="metric,quantity")

    active_orgs = [o for o in orgs if o.get("status") == "active"]
    trial_orgs = [o for o in orgs if o.get("status") == "trialing"]
    past_due = [s for s in subscriptions if s.get("status") == "past_due"]

    usage_totals: dict[str, int] = {}
    for event in usage:
        metric = event.get("metric") or "unknown"
        usage_totals[metric] = usage_totals.get(metric, 0) + int(event.get("quantity") or 0)

    return {
        "organizations_total": len(orgs),
        "organizations_active": len(active_orgs),
        "organizations_trialing": len(trial_orgs),
        "subscriptions_total": len(subscriptions),
        "subscriptions_past_due": len(past_due),
        "usage_30d": usage_totals,
    }


@router.get("/organizations")
def list_platform_organizations(
    status: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    admin: PlatformAdminContext = Depends(require_platform_role()),
):
    filters = {"status": f"eq.{status}"} if status else None
    orgs = db.select("organizations", filters=filters, order="created_at.desc", limit=limit)
    return {"items": orgs, "total": len(orgs)}


@router.get("/organizations/{organization_id}/billing")
def get_org_billing(
    organization_id: str,
    admin: PlatformAdminContext = Depends(require_platform_role("super_admin", "finance", "support")),
):
    subscriptions = db.select("subscriptions", filters={"organization_id": f"eq.{organization_id}"}, limit=1)
    invoices = db.select("invoices", filters={"organization_id": f"eq.{organization_id}"}, order="created_at.desc", limit=20)
    payments = db.select("payments", filters={"organization_id": f"eq.{organization_id}"}, order="created_at.desc", limit=20)
    return {
        "subscription": subscriptions[0] if subscriptions else None,
        "invoices": invoices,
        "payments": payments,
    }


@router.get("/organizations/{organization_id}/usage")
def get_org_usage(
    organization_id: str,
    days: int = Query(default=30, ge=1, le=365),
    admin: PlatformAdminContext = Depends(require_platform_role()),
):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    events = db.select_all(
        "usage_events",
        filters={"organization_id": f"eq.{organization_id}", "created_at": f"gte.{since}"},
        select_cols="metric,quantity,created_at,source,entity,entity_id",
    )
    totals: dict[str, int] = {}
    for event in events:
        metric = event.get("metric") or "unknown"
        totals[metric] = totals.get(metric, 0) + int(event.get("quantity") or 0)
    return {"days": days, "totals": totals, "events": events[:500]}


@router.get("/audit-logs")
def list_audit_logs(
    organization_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    admin: PlatformAdminContext = Depends(require_platform_role("super_admin", "support", "ops")),
):
    filters = {}
    if organization_id:
        filters["organization_id"] = f"eq.{organization_id}"
    if action:
        filters["action"] = f"eq.{action}"
    logs = db.select("audit_logs", filters=filters or None, order="created_at.desc", limit=limit)
    return {"items": logs, "total": len(logs)}

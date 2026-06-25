from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from services.auth import DEFAULT_ORGANIZATION_ID
from services.audit import write_audit_log
from services.platform_auth import PlatformAdminContext, require_platform_role
from services.supabase_client import db

router = APIRouter(prefix="/platform", tags=["platform"])


class PlatformOrganizationCreate(BaseModel):
    name: str
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")
    plan_id: str = "starter"
    owner_email: Optional[str] = None
    owner_name: Optional[str] = None
    status: str = "trialing"
    customer_tier: str = "standard"
    logo_url: Optional[str] = None
    primary_domain: Optional[str] = None
    subdomain: Optional[str] = None
    admin_path: Optional[str] = None
    brand_primary_color: str = "#C9A040"
    brand_secondary_color: str = "#2C1F16"
    brand_accent_color: str = "#FAF7F2"
    public_catalog_enabled: bool = True
    feature_flags: dict = {}
    brand_settings: dict = {}
    internal_notes: Optional[str] = None


class PlatformOrganizationUpdate(BaseModel):
    name: Optional[str] = None
    plan_id: Optional[str] = None
    status: Optional[str] = None
    customer_tier: Optional[str] = None
    logo_url: Optional[str] = None
    primary_domain: Optional[str] = None
    subdomain: Optional[str] = None
    admin_path: Optional[str] = None
    brand_primary_color: Optional[str] = None
    brand_secondary_color: Optional[str] = None
    brand_accent_color: Optional[str] = None
    public_catalog_enabled: Optional[bool] = None
    feature_flags: Optional[dict] = None
    brand_settings: Optional[dict] = None
    internal_notes: Optional[str] = None


def _usage_totals(events: list[dict]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for event in events:
        metric = event.get("metric") or "unknown"
        totals[metric] = totals.get(metric, 0) + int(event.get("quantity") or 0)
    return totals


def _tenant_urls(slug: str, subdomain: Optional[str], primary_domain: Optional[str], admin_path: Optional[str]) -> dict:
    clean_subdomain = subdomain or slug
    return {
        "subdomain": clean_subdomain,
        "primary_domain": primary_domain or f"{clean_subdomain}.polkorp.com",
        "admin_path": admin_path or f"/{slug}/admin",
        "platform_admin_url": "/admin",
        "client_admin_url": admin_path or f"/{slug}/admin",
    }


@router.get("/summary")
def platform_summary(admin: PlatformAdminContext = Depends(require_platform_role())):
    orgs = db.select("organizations", limit=10000)
    subscriptions = db.select("subscriptions", limit=10000)
    usage_30d_since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    usage = db.select_all("usage_events", filters={"created_at": f"gte.{usage_30d_since}"}, select_cols="metric,quantity")

    active_orgs = [o for o in orgs if o.get("status") == "active"]
    trial_orgs = [o for o in orgs if o.get("status") == "trialing"]
    lead_clients = [o for o in orgs if o.get("customer_tier") == "lead_client"]
    kairos_org = next((o for o in orgs if o.get("slug") == "kairos" or o.get("id") == DEFAULT_ORGANIZATION_ID), None)
    past_due = [s for s in subscriptions if s.get("status") == "past_due"]

    return {
        "organizations_total": len(orgs),
        "organizations_active": len(active_orgs),
        "organizations_trialing": len(trial_orgs),
        "lead_clients_total": len(lead_clients),
        "kairos_lead_client": kairos_org,
        "subscriptions_total": len(subscriptions),
        "subscriptions_past_due": len(past_due),
        "usage_30d": _usage_totals(usage),
    }


@router.get("/organizations")
def list_platform_organizations(
    status: Optional[str] = None,
    customer_tier: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    admin: PlatformAdminContext = Depends(require_platform_role()),
):
    filters = {}
    if status:
        filters["status"] = f"eq.{status}"
    if customer_tier:
        filters["customer_tier"] = f"eq.{customer_tier}"
    orgs = db.select("organizations", filters=filters or None, order="created_at.desc", limit=limit)
    return {"items": orgs, "total": len(orgs)}


@router.post("/organizations")
def create_platform_organization(
    body: PlatformOrganizationCreate,
    request: Request,
    admin: PlatformAdminContext = Depends(require_platform_role("super_admin", "ops")),
):
    urls = _tenant_urls(body.slug, body.subdomain, body.primary_domain, body.admin_path)
    existing = db.select("organizations", filters={"slug": f"eq.{body.slug}"}, limit=1)
    if existing:
        raise ValueError("Organization slug already exists")

    organization = db.insert("organizations", {
        "name": body.name,
        "slug": body.slug,
        "plan": body.plan_id,
        "status": body.status,
        "customer_tier": body.customer_tier,
        "logo_url": body.logo_url,
        "primary_domain": urls["primary_domain"],
        "subdomain": urls["subdomain"],
        "admin_path": urls["admin_path"],
        "brand_primary_color": body.brand_primary_color,
        "brand_secondary_color": body.brand_secondary_color,
        "brand_accent_color": body.brand_accent_color,
        "public_catalog_enabled": body.public_catalog_enabled,
        "feature_flags": body.feature_flags,
        "brand_settings": {**body.brand_settings, **urls, "owner_email": body.owner_email, "owner_name": body.owner_name},
        "internal_notes": body.internal_notes,
        "onboarding_status": "invited" if body.owner_email else "draft",
    })

    db.insert("subscriptions", {
        "organization_id": organization["id"],
        "plan_id": body.plan_id,
        "status": body.status,
        "provider": "manual",
    })

    if body.owner_email:
        db.insert("organization_invitations", {
            "organization_id": organization["id"],
            "email": body.owner_email,
            "role": "owner",
            "status": "pending",
        })

    write_audit_log(
        org=None,
        action="platform.organization.create",
        entity="organization",
        entity_id=organization.get("id"),
        metadata={"slug": body.slug, "plan_id": body.plan_id, "actor": admin.email, "client_admin_url": urls["client_admin_url"]},
        request=request,
    )
    return {"organization": organization, "urls": urls}


@router.patch("/organizations/{organization_id}")
def update_platform_organization(
    organization_id: str,
    body: PlatformOrganizationUpdate,
    request: Request,
    admin: PlatformAdminContext = Depends(require_platform_role("super_admin", "ops")),
):
    update_data = body.model_dump(exclude_none=True)
    if "plan_id" in update_data:
        update_data["plan"] = update_data.pop("plan_id")
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        db.update("organizations", organization_id, update_data)
    if body.plan_id:
        rows = db.select("subscriptions", filters={"organization_id": f"eq.{organization_id}"}, limit=1)
        if rows:
            db.update("subscriptions", rows[0]["id"], {"plan_id": body.plan_id, "updated_at": datetime.now(timezone.utc).isoformat()})
    write_audit_log(org=None, action="platform.organization.update", entity="organization", entity_id=organization_id, metadata={"fields": list(update_data.keys()), "actor": admin.email}, request=request)
    org = db.select("organizations", filters={"id": f"eq.{organization_id}"}, limit=1)
    return {"organization": org[0] if org else None}


@router.get("/lead-client")
def get_lead_client(admin: PlatformAdminContext = Depends(require_platform_role())):
    orgs = db.select("organizations", filters={"customer_tier": "eq.lead_client"}, order="created_at.asc", limit=10)
    if not orgs:
        orgs = db.select("organizations", filters={"slug": "eq.kairos"}, limit=1)
    return {"items": orgs, "primary": orgs[0] if orgs else None}


@router.get("/organizations/{organization_id}/billing")
def get_org_billing(
    organization_id: str,
    admin: PlatformAdminContext = Depends(require_platform_role("super_admin", "finance", "support")),
):
    subscriptions = db.select("subscriptions", filters={"organization_id": f"eq.{organization_id}"}, limit=1)
    invoices = db.select("invoices", filters={"organization_id": f"eq.{organization_id}"}, order="created_at.desc", limit=20)
    payments = db.select("payments", filters={"organization_id": f"eq.{organization_id}"}, order="created_at.desc", limit=20)
    return {"subscription": subscriptions[0] if subscriptions else None, "invoices": invoices, "payments": payments}


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
    return {"days": days, "totals": _usage_totals(events), "events": events[:500]}


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

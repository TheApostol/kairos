from __future__ import annotations

import logging
from typing import Any, Optional
from datetime import datetime, timezone

from services.auth import OrgContext
from services.supabase_client import db, ScopedSupabaseClient

logger = logging.getLogger(__name__)


def record_usage(
    *,
    org: OrgContext,
    metric: str,
    quantity: int = 1,
    source: Optional[str] = None,
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Best-effort usage meter.

    Used for billing limits and SaaS analytics. It must never fail the primary
    user action, so exceptions are swallowed intentionally.
    """
    try:
        org.db.insert("usage_events", {
            "actor_user_id": org.user_id,
            "metric": metric,
            "quantity": quantity,
            "source": source,
            "entity": entity,
            "entity_id": str(entity_id) if entity_id is not None else None,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        logger.exception("Failed to record usage event: org=%s metric=%s", org.organization_id, metric)


def get_current_usage(organization_id: str, metric: str, since_iso: Optional[str] = None) -> int:
    filters = {"metric": f"eq.{metric}"}
    if since_iso:
        filters["created_at"] = f"gte.{since_iso}"
    try:
        events = ScopedSupabaseClient(db, organization_id).select_all("usage_events", filters=filters, select_cols="quantity")
        return sum(int(e.get("quantity") or 0) for e in events)
    except Exception:
        logger.exception("Failed to read usage events: org=%s metric=%s", organization_id, metric)
        return 0

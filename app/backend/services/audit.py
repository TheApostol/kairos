from __future__ import annotations

from typing import Any, Optional
from fastapi import Request

from services.auth import OrgContext
from services.supabase_client import db


def _request_meta(request: Optional[Request]) -> tuple[str, str]:
    if not request:
        return "", ""
    forwarded_for = request.headers.get("x-forwarded-for", "")
    ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else "")
    user_agent = request.headers.get("user-agent", "")
    return ip, user_agent


def write_audit_log(
    *,
    org: Optional[OrgContext],
    action: str,
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> None:
    """Best-effort audit writer.

    This must never break the user-facing action. It uses the platform db client
    because audit_logs is an ops table, but always writes organization_id and
    actor fields from OrgContext when available.
    """
    ip, user_agent = _request_meta(request)
    try:
        db.insert("audit_logs", {
            "organization_id": org.organization_id if org else None,
            "actor_user_id": org.user_id if org else None,
            "actor_email": org.email if org else None,
            "actor_role": org.role if org else None,
            "action": action,
            "entity": entity,
            "entity_id": str(entity_id) if entity_id is not None else None,
            "ip_address": ip,
            "user_agent": user_agent,
            "metadata": metadata or {},
        })
    except Exception:
        pass

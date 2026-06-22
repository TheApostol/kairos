from __future__ import annotations

from fastapi import Depends, HTTPException, status

from services.auth import get_current_user
from services.supabase_client import db


class PlatformAdminContext:
    def __init__(self, user_id: str, email: str, role: str):
        self.user_id = user_id
        self.email = email
        self.role = role


def require_platform_role(*roles: str):
    """Require a platform-level admin role, independent of tenant membership."""
    allowed = set(roles) if roles else {"super_admin", "support", "finance", "ops"}

    def checker(user_and_token=Depends(get_current_user)) -> PlatformAdminContext:
        user, _ = user_and_token
        user_id = user.get("id")
        email = user.get("email", "")
        rows = db.select(
            "platform_admins",
            filters={"user_id": f"eq.{user_id}", "status": "eq.active"},
            select_cols="role,status",
            limit=1,
        )
        if not rows or rows[0].get("role") not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin access required")
        return PlatformAdminContext(user_id=user_id, email=email, role=rows[0]["role"])

    return checker

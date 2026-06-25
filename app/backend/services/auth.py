import httpx
from fastapi import Depends, Header, HTTPException, Query, status

from config import settings
from services.supabase_client import ScopedSupabaseClient, db

DEFAULT_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"


def _supabase_anon_key() -> str:
    return settings.SUPABASE_ANON_KEY or settings.SUPABASE_KEY


def _verify_access_token(token: str) -> dict:
    """Verify a Supabase Auth access token and return the user record."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": _supabase_anon_key(),
                },
            )
    except httpx.HTTPError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth service unavailable")

    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    return resp.json()


def call_rpc(token: str, fn_name: str, params: dict):
    """Call a Postgres RPC as the given user. SECURITY DEFINER functions like
    create_organization/accept_invitation rely on auth.uid(), which requires
    the caller's own JWT (not the service-role key)."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/rpc/{fn_name}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": _supabase_anon_key(),
                    "Content-Type": "application/json",
                },
                json=params,
            )
    except httpx.HTTPError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth service unavailable")

    if not resp.is_success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=resp.text[:300])
    return resp.json() if resp.text else None


def _claim_default_organization(token: str) -> None:
    """Let the first-ever signed-in user claim ownership of the pre-existing
    default organization, so they see the existing data instead of an empty
    workspace."""
    try:
        with httpx.Client(timeout=10) as client:
            client.post(
                f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/rpc/claim_default_organization",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": _supabase_anon_key(),
                    "Content-Type": "application/json",
                },
                json={},
            )
    except httpx.HTTPError:
        pass


class OrgContext:
    def __init__(self, user_id: str, email: str, organization_id: str, role: str, access_token: str = ""):
        self.user_id = user_id
        self.email = email
        self.organization_id = organization_id
        self.role = role
        self.access_token = access_token

    @property
    def db(self) -> ScopedSupabaseClient:
        return ScopedSupabaseClient(db, self.organization_id)


def get_current_user(authorization: str = Header(default=None)) -> tuple[dict, str]:
    """Verify the bearer token without requiring organization membership.
    Used for bootstrap endpoints (create org, accept invitation)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    user = _verify_access_token(token)
    return user, token


def get_current_org(authorization: str = Header(default=None), token: str = Query(default=None)) -> OrgContext:
    """Resolve the calling user's organization. Accepts the access token either
    as a Bearer header (normal requests) or a `token` query parameter (for
    EventSource/SSE connections, which cannot set custom headers)."""
    if authorization and authorization.lower().startswith("bearer "):
        access_token = authorization.split(" ", 1)[1].strip()
    elif token:
        access_token = token
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    user = _verify_access_token(access_token)
    user_id = user["id"]
    email = user.get("email", "")

    memberships = db.select(
        "organization_users",
        filters={"user_id": f"eq.{user_id}", "status": "eq.active"},
        select_cols="organization_id,role",
    )

    if not memberships:
        _claim_default_organization(access_token)
        memberships = db.select(
            "organization_users",
            filters={"user_id": f"eq.{user_id}", "status": "eq.active"},
            select_cols="organization_id,role",
        )

    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not a member of any organization yet. Ask an admin for an invite.",
        )

    membership = memberships[0]
    return OrgContext(
        user_id=user_id,
        email=email,
        organization_id=membership["organization_id"],
        role=membership["role"],
        access_token=access_token,
    )


def get_organization_row(organization_id: str, select_cols: str = "*") -> dict | None:
    """Fetch a single organization's own row by id. Safe outside ScopedSupabaseClient
    because the filter is the org's own id, not a cross-tenant query."""
    rows = db.select("organizations", filters={"id": f"eq.{organization_id}"}, select_cols=select_cols, limit=1)
    return rows[0] if rows else None


def update_organization_row(organization_id: str, data: dict) -> dict:
    return db.update("organizations", organization_id, data)


def list_organizations_with_sheet() -> list[dict]:
    """All organizations that have a Google Sheet connected — used by the
    cross-tenant auto-sync background loop (main.py), which by nature can't
    go through a single-org ScopedSupabaseClient."""
    return db.select(
        "organizations",
        filters={"google_sheet_id": "not.is.null"},
        select_cols="id,google_sheet_id",
    )


def require_role(*roles: str):
    def checker(org: OrgContext = Depends(get_current_org)) -> OrgContext:
        if org.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions for this action")
        return org

    return checker

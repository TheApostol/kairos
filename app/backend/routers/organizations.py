from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import settings
from services.auth import OrgContext, get_current_org, get_current_user, call_rpc, require_role
from services.supabase_client import db

router = APIRouter(prefix="/organizations", tags=["organizations"])


VALID_INVITE_ROLES = {"admin", "sales", "viewer"}
VALID_MEMBER_ROLES = {"owner", "admin", "sales", "viewer"}
VALID_MEMBER_STATUSES = {"active", "disabled"}


class OrganizationCreate(BaseModel):
    name: str
    slug: str


class InvitationCreate(BaseModel):
    email: str
    role: str = "sales"


class AcceptInvitation(BaseModel):
    token: str


class MemberUpdate(BaseModel):
    role: Optional[str] = None
    status: Optional[str] = None


def _admin_get_user_email(user_id: str) -> str:
    """Look up a user's email via the Supabase Auth admin API."""
    import httpx

    key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY
    if not key:
        return ""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users/{user_id}",
                headers={"Authorization": f"Bearer {key}", "apikey": key},
            )
        if resp.status_code == 200:
            return resp.json().get("email", "")
    except httpx.HTTPError:
        pass
    return ""


def _send_invitation_email(email: str, organization_name: str, role: str, token: str) -> None:
    if not settings.BREVO_API_KEY:
        return
    import httpx

    invite_url = f"{settings.FRONTEND_URL.rstrip('/')}/accept-invite?token={token}"
    try:
        with httpx.Client(timeout=15) as client:
            client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": settings.BREVO_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "sender": {"name": settings.SENDER_NAME, "email": settings.SENDER_EMAIL},
                    "to": [{"email": email}],
                    "subject": f"Te invitaron a unirte a {organization_name} en Kairos",
                    "htmlContent": (
                        f"<p>Te invitaron a unirte a <strong>{organization_name}</strong> "
                        f"como <strong>{role}</strong> en Kairos CRM.</p>"
                        f"<p><a href=\"{invite_url}\">Aceptar invitación</a></p>"
                    ),
                    "textContent": f"Te invitaron a unirte a {organization_name} como {role}. Aceptá aquí: {invite_url}",
                },
            )
    except httpx.HTTPError:
        pass


@router.get("/me")
def get_my_organization(current_org: OrgContext = Depends(get_current_org)):
    orgs = db.select("organizations", filters={"id": f"eq.{current_org.organization_id}"}, limit=1)
    if not orgs:
        raise HTTPException(status_code=404, detail="Organization not found")

    members = db.select(
        "organization_users",
        filters={"organization_id": f"eq.{current_org.organization_id}"},
        select_cols="user_id,role,status,created_at",
        order="created_at.asc",
    )
    for member in members:
        member["email"] = _admin_get_user_email(member["user_id"])

    return {
        "organization": orgs[0],
        "role": current_org.role,
        "user_id": current_org.user_id,
        "email": current_org.email,
        "members": members,
    }


@router.post("")
def create_new_organization(body: OrganizationCreate, user_and_token=Depends(get_current_user)):
    _, token = user_and_token
    name = body.name.strip()
    slug = body.slug.strip().lower()
    if not name or not slug:
        raise HTTPException(status_code=400, detail="Name and slug are required")

    new_org_id = call_rpc(token, "create_organization", {"org_name": name, "org_slug": slug})
    return {"organization_id": new_org_id}


@router.post("/accept-invitation")
def accept_invitation(body: AcceptInvitation, user_and_token=Depends(get_current_user)):
    _, token = user_and_token
    org_id = call_rpc(token, "accept_invitation", {"invite_token": body.token})
    return {"organization_id": org_id}


@router.get("/invitations")
def list_invitations(current_org: OrgContext = Depends(require_role("owner", "admin"))):
    invitations = db.select(
        "organization_invitations",
        filters={"organization_id": f"eq.{current_org.organization_id}", "accepted_at": "is.null"},
        order="created_at.desc",
    )
    return {"items": invitations}


@router.post("/invitations")
def create_invitation(body: InvitationCreate, current_org: OrgContext = Depends(require_role("owner", "admin"))):
    role = body.role.strip().lower()
    if role not in VALID_INVITE_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(VALID_INVITE_ROLES)}")

    email = body.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    invitation = db.insert("organization_invitations", {
        "organization_id": current_org.organization_id,
        "email": email,
        "role": role,
        "created_by": current_org.user_id,
    })

    orgs = db.select("organizations", filters={"id": f"eq.{current_org.organization_id}"}, limit=1)
    org_name = orgs[0]["name"] if orgs else "Kairos"
    _send_invitation_email(email, org_name, role, invitation["token"])

    return invitation


@router.delete("/invitations/{invitation_id}")
def revoke_invitation(invitation_id: str, current_org: OrgContext = Depends(require_role("owner", "admin"))):
    db.delete("organization_invitations", invitation_id, extra_filters={"organization_id": f"eq.{current_org.organization_id}"})
    return {"ok": True}


def _active_owner_count(organization_id: str) -> int:
    owners = db.select(
        "organization_users",
        filters={"organization_id": f"eq.{organization_id}", "role": "eq.owner", "status": "eq.active"},
        select_cols="user_id",
    )
    return len(owners)


@router.patch("/members/{user_id}")
def update_member(user_id: str, body: MemberUpdate, current_org: OrgContext = Depends(require_role("owner", "admin"))):
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "role" in update_data and update_data["role"] not in VALID_MEMBER_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(VALID_MEMBER_ROLES)}")
    if "status" in update_data and update_data["status"] not in VALID_MEMBER_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(VALID_MEMBER_STATUSES)}")

    members = db.select(
        "organization_users",
        filters={"organization_id": f"eq.{current_org.organization_id}", "user_id": f"eq.{user_id}"},
        limit=1,
    )
    if not members:
        raise HTTPException(status_code=404, detail="Member not found")
    member = members[0]

    demoting_owner = member["role"] == "owner" and (
        update_data.get("role", "owner") != "owner" or update_data.get("status", "active") != "active"
    )
    if demoting_owner and _active_owner_count(current_org.organization_id) <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the last owner of the organization")

    db.update("organization_users", member["id"], update_data)
    return {"ok": True}


@router.delete("/members/{user_id}")
def remove_member(user_id: str, current_org: OrgContext = Depends(require_role("owner", "admin"))):
    members = db.select(
        "organization_users",
        filters={"organization_id": f"eq.{current_org.organization_id}", "user_id": f"eq.{user_id}"},
        limit=1,
    )
    if not members:
        raise HTTPException(status_code=404, detail="Member not found")
    member = members[0]

    if member["role"] == "owner" and _active_owner_count(current_org.organization_id) <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the last owner of the organization")

    db.delete("organization_users", member["id"])
    return {"ok": True}

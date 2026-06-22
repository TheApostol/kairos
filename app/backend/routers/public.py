from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from services.supabase_client import db

router = APIRouter(prefix="/public", tags=["public"])

# Unprefixed router for unauthenticated endpoints whose URL path is owned by
# another router's namespace (e.g. the email tracking pixel lives under
# /campaigns/track/... since that's where campaigns.py builds the URL).
tracking_router = APIRouter(tags=["public"])

DEFAULT_ORG_SLUG = "kairos"

_TRACKING_PIXEL_GIF = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
    b"\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00"
    b"\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
    b"\x44\x01\x00\x3b"
)


@tracking_router.get("/campaigns/track/{campaign_id}/{send_id}")
def track_open(campaign_id: str, send_id: str):
    """Email open tracking pixel — loaded by the recipient's email client with
    no auth context, so this uses the global `db` directly rather than an
    org-scoped client; it only flips a flag and increments a counter, no
    lead/campaign data is read back to the caller."""
    try:
        sends = db.select("campaign_sends", filters={"id": f"eq.{send_id}", "campaign_id": f"eq.{campaign_id}"}, limit=1)
        if sends and not sends[0].get("abierto_at"):
            now_str = datetime.now(timezone.utc).isoformat()
            db.update("campaign_sends", send_id, {"abierto_at": now_str, "estado": "abierto"})
            camps = db.select("campaigns", filters={"id": f"eq.{campaign_id}"}, limit=1)
            if camps:
                current = int(camps[0].get("abiertos") or 0)
                db.update("campaigns", campaign_id, {"abiertos": current + 1})
    except Exception:
        pass
    return Response(content=_TRACKING_PIXEL_GIF, media_type="image/gif",
                     headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


@router.get("/catalog")
def get_public_catalog(org: str = Query(default=DEFAULT_ORG_SLUG)):
    """Unauthenticated, org-scoped product catalog for the public catalog page."""
    orgs = db.select("organizations", filters={"slug": f"eq.{org}"}, limit=1)
    if not orgs:
        raise HTTPException(status_code=404, detail="Organization not found")

    organization = orgs[0]
    if not organization.get("public_catalog_enabled", True):
        raise HTTPException(status_code=404, detail="Catalog not available")

    products = db.select_all(
        "products",
        filters={"organization_id": f"eq.{organization['id']}", "activo": "eq.true"},
        select_cols="id,nombre,descripcion,categoria,precio_minorista,precio_mayorista,stock,imagen_url,orden",
    )
    products.sort(key=lambda p: (p.get("orden") is None, p.get("orden") or 0, p.get("nombre") or ""))

    return {
        "items": products,
        "organization": {"name": organization["name"], "slug": organization["slug"]},
    }

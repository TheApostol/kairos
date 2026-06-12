from fastapi import APIRouter, HTTPException, Query

from services.supabase_client import db

router = APIRouter(prefix="/public", tags=["public"])

DEFAULT_ORG_SLUG = "kairos"


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

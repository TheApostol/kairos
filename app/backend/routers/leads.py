import csv
import io
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime

from app.backend.services.supabase_client import db

router = APIRouter(prefix="/leads", tags=["leads"])


class LeadUpdate(BaseModel):
    estado: Optional[str] = None
    observaciones: Optional[str] = None
    asignado_a: Optional[str] = None


@router.get("")
def list_leads(
    rubro: Optional[str] = None,
    provincia: Optional[str] = None,
    ciudad: Optional[str] = None,
    estado: Optional[str] = None,
    score_min: Optional[float] = None,
    score_max: Optional[float] = None,
    has_email: Optional[bool] = None,
    has_phone: Optional[bool] = None,
    q: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
):
    params = {"select": "*", "order": "created_at.desc"}

    if rubro:
        params["rubro"] = f"ilike.%{rubro}%"
    if provincia:
        params["provincia"] = f"ilike.%{provincia}%"
    if ciudad:
        params["ciudad"] = f"ilike.%{ciudad}%"
    if estado:
        params["estado"] = f"eq.{estado}"
    if score_min is not None:
        params["score_ia"] = f"gte.{score_min}"
    if score_max is not None:
        # if score_min was already set, we need gte and lte together
        # Supabase supports multiple filters by repeating query keys
        # We'll handle this via raw URL approach
        existing = params.get("score_ia", "")
        if existing:
            params["score_ia"] = f"gte.{score_min}"
            params["score_ia_lte"] = f"lte.{score_max}"
        else:
            params["score_ia"] = f"lte.{score_max}"
    if has_email is True:
        params["email"] = "neq."
    elif has_email is False:
        params["email"] = "eq."
    if has_phone is True:
        params["telefono"] = "neq."
    elif has_phone is False:
        params["telefono"] = "eq."
    if q:
        params["empresa"] = f"ilike.%{q}%"

    offset = (page - 1) * per_page
    params["limit"] = per_page
    params["offset"] = offset

    leads = db.raw_select("leads", params)
    return {"data": leads, "page": page, "per_page": per_page, "count": len(leads)}


@router.get("/stats")
def get_leads_stats():
    all_leads = db.select("leads", limit=10000)

    by_estado: dict = {}
    by_provincia: dict = {}
    by_rubro: dict = {}
    score_dist = {"0-3": 0, "4-6": 0, "7-8": 0, "9-10": 0}

    for lead in all_leads:
        estado = lead.get("estado") or "sin_estado"
        by_estado[estado] = by_estado.get(estado, 0) + 1

        prov = lead.get("provincia") or "desconocida"
        by_provincia[prov] = by_provincia.get(prov, 0) + 1

        rubro = lead.get("rubro") or "sin_rubro"
        by_rubro[rubro] = by_rubro.get(rubro, 0) + 1

        score = lead.get("score_ia")
        try:
            score = float(score) if score is not None else 0
        except (ValueError, TypeError):
            score = 0

        if score <= 3:
            score_dist["0-3"] += 1
        elif score <= 6:
            score_dist["4-6"] += 1
        elif score <= 8:
            score_dist["7-8"] += 1
        else:
            score_dist["9-10"] += 1

    return {
        "total": len(all_leads),
        "by_estado": by_estado,
        "by_provincia": by_provincia,
        "by_rubro": by_rubro,
        "score_distribution": score_dist,
    }


@router.get("/export")
def export_leads_csv(
    rubro: Optional[str] = None,
    provincia: Optional[str] = None,
    estado: Optional[str] = None,
):
    params = {"select": "*", "order": "created_at.desc", "limit": 10000}

    if rubro:
        params["rubro"] = f"ilike.%{rubro}%"
    if provincia:
        params["provincia"] = f"ilike.%{provincia}%"
    if estado:
        params["estado"] = f"eq.{estado}"

    leads = db.raw_select("leads", params)

    fieldnames = [
        "id", "empresa", "rubro", "direccion", "ciudad", "provincia",
        "telefono", "website", "google_maps_url", "rating", "reviews_count",
        "price_level", "horarios", "instagram", "email", "whatsapp",
        "score_ia", "observaciones", "fuente", "fecha_extraccion",
        "estado", "asignado_a", "ultima_actividad", "created_at",
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for lead in leads:
        writer.writerow(lead)

    output.seek(0)
    filename = f"leads_kairos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{lead_id}")
def get_lead(lead_id: str):
    leads = db.select("leads", filters={"id": f"eq.{lead_id}"}, limit=1)
    if not leads:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead = leads[0]

    activities = db.select(
        "activities",
        filters={"lead_id": f"eq.{lead_id}"},
        order="created_at.desc",
        limit=50,
    )

    lead["activities"] = activities
    return lead


@router.put("/{lead_id}")
def update_lead(lead_id: str, body: LeadUpdate):
    leads = db.select("leads", filters={"id": f"eq.{lead_id}"}, limit=1)
    if not leads:
        raise HTTPException(status_code=404, detail="Lead not found")

    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_data["updated_at"] = datetime.utcnow().isoformat()
    update_data["ultima_actividad"] = datetime.utcnow().isoformat()

    updated = db.update("leads", lead_id, update_data)
    return updated

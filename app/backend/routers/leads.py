import csv
import io
import math
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime

from services.supabase_client import db

router = APIRouter(prefix="/leads", tags=["leads"])


class LeadUpdate(BaseModel):
    estado: Optional[str] = None
    observaciones: Optional[str] = None
    asignado_a: Optional[str] = None


class TaskCreate(BaseModel):
    titulo: str
    descripcion: Optional[str] = None
    fecha_vencimiento: Optional[str] = None


class TaskUpdate(BaseModel):
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    completado: Optional[bool] = None


def _build_filters(
    empresa: Optional[str],
    rubro: Optional[str],
    provincia: Optional[str],
    ciudad: Optional[str],
    estado: Optional[str],
    con_email: Optional[bool],
    con_telefono: Optional[bool],
    score_min: Optional[float],
    score_max: Optional[float],
    tipo_cliente: Optional[str] = None,
) -> dict:
    params: dict = {"select": "*", "order": "created_at.desc"}
    if empresa:
        params["empresa"] = f"ilike.%{empresa}%"
    if rubro:
        params["rubro"] = f"ilike.%{rubro}%"
    if provincia:
        params["provincia"] = f"ilike.%{provincia}%"
    if ciudad:
        params["ciudad"] = f"ilike.%{ciudad}%"
    if estado:
        params["estado"] = f"eq.{estado}"
    if con_email is True:
        params["email"] = "not.is.null"
    if con_telefono is True:
        params["telefono"] = "not.is.null"
    if score_min is not None:
        params["score_ia"] = f"gte.{int(score_min)}"
    if score_max is not None:
        params["score_ia"] = f"lte.{int(score_max)}"
    if tipo_cliente:
        params["tipo_cliente"] = f"eq.{tipo_cliente}"
    return params


@router.get("")
def list_leads(
    empresa: Optional[str] = None,
    rubro: Optional[str] = None,
    provincia: Optional[str] = None,
    ciudad: Optional[str] = None,
    estado: Optional[str] = None,
    con_email: Optional[bool] = None,
    con_telefono: Optional[bool] = None,
    score_min: Optional[float] = None,
    score_max: Optional[float] = None,
    tipo_cliente: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
):
    params = _build_filters(empresa, rubro, provincia, ciudad, estado, con_email, con_telefono, score_min, score_max, tipo_cliente)

    # Count with same filters (excluding pagination params)
    count_filters = {k: v for k, v in params.items() if k not in ("select", "order")}
    total = db.count("leads", count_filters) if count_filters else db.count("leads")

    params["limit"] = limit
    params["offset"] = (page - 1) * limit

    leads = db.raw_select("leads", params)

    # Map score_ia → score for frontend
    for lead in leads:
        if "score_ia" in lead:
            lead["score"] = lead["score_ia"]

    pages = max(1, math.ceil(total / limit))
    return {"items": leads, "total": total, "page": page, "pages": pages}


@router.get("/stats")
def get_leads_stats():
    all_leads = db.select_all("leads", select_cols="estado,provincia,email")

    by_estado: dict = {}
    by_provincia: dict = {}
    con_email = 0

    for lead in all_leads:
        estado = lead.get("estado") or "nuevo"
        by_estado[estado] = by_estado.get(estado, 0) + 1

        prov = lead.get("provincia") or "Desconocida"
        by_provincia[prov] = by_provincia.get(prov, 0) + 1

        if lead.get("email"):
            con_email += 1

    por_provincia = sorted(
        [{"provincia": k, "count": v} for k, v in by_provincia.items()],
        key=lambda x: x["count"],
        reverse=True,
    )
    por_estado = [{"estado": k, "count": v} for k, v in by_estado.items()]

    return {
        "total": len(all_leads),
        "con_email": con_email,
        "por_provincia": por_provincia,
        "por_estado": por_estado,
    }


@router.get("/export")
def export_leads_csv(
    empresa: Optional[str] = None,
    rubro: Optional[str] = None,
    provincia: Optional[str] = None,
    estado: Optional[str] = None,
    con_email: Optional[bool] = None,
    con_telefono: Optional[bool] = None,
):
    params = _build_filters(empresa, rubro, provincia, ciudad=None, estado=estado,
                            con_email=con_email, con_telefono=con_telefono,
                            score_min=None, score_max=None)
    params["limit"] = 10000

    leads = db.raw_select("leads", params)

    fieldnames = [
        "empresa", "rubro", "direccion", "ciudad", "provincia",
        "telefono", "website", "google_maps_url", "rating", "reviews_count",
        "instagram", "email", "whatsapp", "score_ia", "observaciones",
        "fuente", "fecha_extraccion", "estado",
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


@router.get("/rubros")
def get_rubros():
    leads = db.select_all("leads", select_cols="rubro")
    rubros = sorted({l.get("rubro") for l in leads if l.get("rubro")})
    return {"rubros": rubros}


@router.get("/tasks/today")
def get_today_tasks():
    today = datetime.utcnow().date().isoformat()
    tasks = db.raw_select("tasks", {
        "select": "*",
        "completado": "eq.false",
        "fecha_vencimiento": f"lte.{today}",
        "order": "fecha_vencimiento.asc",
        "limit": 50,
    })
    return {"tasks": tasks, "total": len(tasks)}


@router.post("/import")
async def import_leads_csv(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8-sig")  # utf-8-sig handles Excel BOM
    reader = csv.DictReader(io.StringIO(text))

    # Normalize column names: strip whitespace, lowercase
    inserted = 0
    skipped = 0
    errors = []

    FIELD_MAP = {
        "empresa": ["empresa", "nombre", "name", "company"],
        "telefono": ["telefono", "teléfono", "phone", "tel"],
        "email": ["email", "correo", "mail"],
        "ciudad": ["ciudad", "city"],
        "provincia": ["provincia", "province", "estado"],
        "rubro": ["rubro", "categoria", "category", "industry"],
        "website": ["website", "web", "url", "sitio"],
        "observaciones": ["observaciones", "notas", "notes", "comments"],
    }

    for row in reader:
        row_lower = {k.strip().lower(): v.strip() for k, v in row.items() if k}

        record = {"estado": "nuevo", "fuente": "CSV Import"}
        for field, aliases in FIELD_MAP.items():
            for alias in aliases:
                if alias in row_lower and row_lower[alias]:
                    record[field] = row_lower[alias]
                    break

        if not record.get("empresa"):
            skipped += 1
            continue

        # Deduplicate by empresa name
        try:
            existing = db.select("leads", filters={"empresa": f"eq.{record['empresa']}"}, limit=1)
            if existing:
                skipped += 1
                continue
            db.insert("leads", record)
            inserted += 1
        except Exception as e:
            errors.append(str(e)[:100])

    return {"inserted": inserted, "skipped": skipped, "errors": errors[:5]}


@router.post("/{lead_id}/tasks")
def create_task(lead_id: str, body: TaskCreate):
    task = db.insert("tasks", {
        "lead_id": lead_id,
        "titulo": body.titulo,
        "descripcion": body.descripcion,
        "fecha_vencimiento": body.fecha_vencimiento,
        "completado": False,
        "created_at": datetime.utcnow().isoformat(),
    })
    return task


@router.get("/{lead_id}/tasks")
def get_tasks(lead_id: str):
    tasks = db.select("tasks", filters={"lead_id": f"eq.{lead_id}"}, order="fecha_vencimiento.asc.nullslast")
    return tasks


@router.patch("/{lead_id}/tasks/{task_id}")
def update_task(lead_id: str, task_id: str, body: TaskUpdate):
    update_data = body.model_dump(exclude_none=True)
    updated = db.update("tasks", task_id, update_data)
    return updated


@router.get("/{lead_id}")
def get_lead(lead_id: str):
    leads = db.select("leads", filters={"id": f"eq.{lead_id}"}, limit=1)
    if not leads:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = leads[0]
    if "score_ia" in lead:
        lead["score"] = lead["score_ia"]
    try:
        activities = db.select(
            "activities",
            filters={"lead_id": f"eq.{lead_id}"},
            order="created_at.desc",
            limit=50,
        )
        lead["activities"] = activities
    except Exception:
        lead["activities"] = []
    return lead


@router.patch("/{lead_id}")
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

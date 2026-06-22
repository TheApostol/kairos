import csv
import io
import math
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, UploadFile, File, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime

from services.auth import OrgContext, get_current_org
from services.audit import write_audit_log
from services.billing import assert_plan_allows
from services.usage import record_usage

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


class NoteCreate(BaseModel):
    text: str


ESTADO_CLOSENESS_RANK = {
    "interesado": 0,
    "contactado": 1,
    "nuevo": 2,
    "cliente": 3,
    "descartado": 4,
}

SORT_ORDERS = {
    "recientes": "created_at.desc",
    "score_desc": "score_ia.desc.nullslast",
    "rubro": "rubro.asc.nullslast",
    "empresa": "empresa.asc",
}


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
    sort: Optional[str] = None
) -> dict:
    order = SORT_ORDERS.get(sort, SORT_ORDERS["recientes"])
    params: dict = {"select": "*", "order": order}
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
    if score_min is not None and score_max is not None:
        params["and"] = f"(score_ia.gte.{int(score_min)},score_ia.lte.{int(score_max)})"
    elif score_min is not None:
        params["score_ia"] = f"gte.{int(score_min)}"
    elif score_max is not None:
        params["score_ia"] = f"lte.{int(score_max)}"
    if tipo_cliente:
        params["tipo_cliente"] = f"eq.{tipo_cliente}"
    return params


def _require_lead(current_org: OrgContext, lead_id: str) -> dict:
    leads = current_org.db.select("leads", filters={"id": f"eq.{lead_id}"}, limit=1)
    if not leads:
        raise HTTPException(status_code=404, detail="Lead not found")
    return leads[0]


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
    sort: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    current_org: OrgContext = Depends(get_current_org),
):
    params = _build_filters(empresa, rubro, provincia, ciudad, estado, con_email, con_telefono, score_min, score_max, tipo_cliente, sort)
    count_filters = {k: v for k, v in params.items() if k not in ("select", "order")}
    total = current_org.db.count("leads", count_filters) if count_filters else current_org.db.count("leads")

    if sort == "cercania":
        fetch_params = {**params, "limit": 5000, "offset": 0}
        all_leads = current_org.db.raw_select("leads", fetch_params)
        all_leads.sort(key=lambda l: ESTADO_CLOSENESS_RANK.get(l.get("estado") or "nuevo", 99))
        start = (page - 1) * limit
        leads = all_leads[start:start + limit]
    else:
        params["limit"] = limit
        params["offset"] = (page - 1) * limit
        leads = current_org.db.raw_select("leads", params)

    for lead in leads:
        if "score_ia" in lead:
            lead["score"] = lead["score_ia"]

    pages = max(1, math.ceil(total / limit))
    return {"items": leads, "total": total, "page": page, "pages": pages}


@router.get("/stats")
def get_leads_stats(current_org: OrgContext = Depends(get_current_org)):
    all_leads = current_org.db.select_all("leads", select_cols="estado,provincia,email,whatsapp")
    by_estado: dict = {}
    by_provincia: dict = {}
    con_email = 0
    con_whatsapp = 0

    for lead in all_leads:
        estado = lead.get("estado") or "nuevo"
        by_estado[estado] = by_estado.get(estado, 0) + 1
        prov = lead.get("provincia") or "Desconocida"
        by_provincia[prov] = by_provincia.get(prov, 0) + 1
        if lead.get("email"):
            con_email += 1
        if lead.get("whatsapp"):
            con_whatsapp += 1

    por_provincia = sorted(
        [{"provincia": k, "count": v} for k, v in by_provincia.items()],
        key=lambda x: x["count"],
        reverse=True,
    )
    por_estado = [{"estado": k, "count": v} for k, v in by_estado.items()]
    return {
        "total": len(all_leads),
        "con_email": con_email,
        "con_whatsapp": con_whatsapp,
        "por_provincia": por_provincia,
        "por_estado": por_estado,
    }


@router.get("/export")
def export_leads_csv(
    request: Request,
    empresa: Optional[str] = None,
    rubro: Optional[str] = None,
    provincia: Optional[str] = None,
    estado: Optional[str] = None,
    con_email: Optional[bool] = None,
    con_telefono: Optional[bool] = None,
    current_org: OrgContext = Depends(get_current_org),
):
    params = _build_filters(empresa, rubro, provincia, ciudad=None, estado=estado,
                            con_email=con_email, con_telefono=con_telefono,
                            score_min=None, score_max=None)
    params["limit"] = 10000
    leads = current_org.db.raw_select("leads", params)

    write_audit_log(
        org=current_org,
        action="leads.export_csv",
        entity="leads",
        metadata={"count": len(leads), "filters": {"empresa": empresa, "rubro": rubro, "provincia": provincia, "estado": estado}},
        request=request,
    )
    record_usage(org=current_org, metric="exports", source="leads", entity="leads", quantity=1)

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
def get_rubros(current_org: OrgContext = Depends(get_current_org)):
    leads = current_org.db.select_all("leads", select_cols="rubro")
    rubros = sorted({l.get("rubro") for l in leads if l.get("rubro")})
    return {"rubros": rubros}


@router.get("/tasks/today")
def get_today_tasks(current_org: OrgContext = Depends(get_current_org)):
    today = datetime.utcnow().date().isoformat()
    tasks = current_org.db.raw_select("tasks", {
        "select": "*",
        "completado": "eq.false",
        "fecha_vencimiento": f"lte.{today}",
        "order": "fecha_vencimiento.asc",
        "limit": 50,
    })
    return {"tasks": tasks, "total": len(tasks)}


@router.post("/import")
async def import_leads_csv(request: Request, file: UploadFile = File(...), current_org: OrgContext = Depends(get_current_org)):
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    rows = list(reader)
    # Reject outright if the batch can't possibly fit, before doing any work.
    assert_plan_allows(current_org, "leads", quantity=len(rows), period="none")

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

    for row in rows:
        row_lower = {k.strip().lower(): v.strip() for k, v in row.items() if k and v is not None}
        record = {"estado": "nuevo", "fuente": "CSV Import"}
        for field, aliases in FIELD_MAP.items():
            for alias in aliases:
                if alias in row_lower and row_lower[alias]:
                    record[field] = row_lower[alias]
                    break

        if not record.get("empresa"):
            skipped += 1
            continue

        try:
            # Re-check per-row rather than relying on the upfront batch check
            # alone — narrows the window for a concurrent import (or another
            # request) to push the org over the limit between the upfront
            # check and this row's insert.
            assert_plan_allows(current_org, "leads", quantity=1, period="none")
        except HTTPException:
            errors.append("plan_limit_exceeded: remaining rows skipped")
            break

        try:
            existing = current_org.db.select("leads", filters={"empresa": f"eq.{record['empresa']}"}, limit=1)
            if existing:
                skipped += 1
                continue
            current_org.db.insert("leads", record)
            inserted += 1
        except Exception as e:
            errors.append(str(e)[:100])

    if inserted:
        record_usage(org=current_org, metric="leads", quantity=inserted, source="csv_import", entity="leads")
    write_audit_log(
        org=current_org,
        action="leads.import_csv",
        entity="leads",
        metadata={"inserted": inserted, "skipped": skipped, "errors": len(errors), "filename": file.filename},
        request=request,
    )
    return {"inserted": inserted, "skipped": skipped, "errors": errors[:5]}


@router.post("/{lead_id}/tasks")
def create_task(request: Request, lead_id: str, body: TaskCreate, current_org: OrgContext = Depends(get_current_org)):
    _require_lead(current_org, lead_id)
    task = current_org.db.insert("tasks", {
        "lead_id": lead_id,
        "titulo": body.titulo,
        "descripcion": body.descripcion,
        "fecha_vencimiento": body.fecha_vencimiento,
        "completado": False,
        "created_at": datetime.utcnow().isoformat(),
    })
    write_audit_log(org=current_org, action="lead.task.create", entity="task", entity_id=task.get("id"), metadata={"lead_id": lead_id}, request=request)
    return task


@router.get("/{lead_id}/tasks")
def get_tasks(lead_id: str, current_org: OrgContext = Depends(get_current_org)):
    _require_lead(current_org, lead_id)
    return current_org.db.select("tasks", filters={"lead_id": f"eq.{lead_id}"}, order="fecha_vencimiento.asc.nullslast")


@router.patch("/{lead_id}/tasks/{task_id}")
def update_task(request: Request, lead_id: str, task_id: str, body: TaskUpdate, current_org: OrgContext = Depends(get_current_org)):
    _require_lead(current_org, lead_id)
    update_data = body.model_dump(exclude_none=True)
    updated = current_org.db.update("tasks", task_id, update_data)
    write_audit_log(org=current_org, action="lead.task.update", entity="task", entity_id=task_id, metadata={"lead_id": lead_id, "fields": list(update_data.keys())}, request=request)
    return updated


@router.post("/{lead_id}/notes")
def create_note(request: Request, lead_id: str, body: NoteCreate, current_org: OrgContext = Depends(get_current_org)):
    _require_lead(current_org, lead_id)
    note = current_org.db.insert("lead_notes", {
        "lead_id": lead_id,
        "texto": body.text,
        "created_at": datetime.utcnow().isoformat(),
    })
    write_audit_log(org=current_org, action="lead.note.create", entity="lead_note", entity_id=note.get("id"), metadata={"lead_id": lead_id}, request=request)
    return note


@router.get("/{lead_id}/notes")
def get_notes(lead_id: str, current_org: OrgContext = Depends(get_current_org)):
    _require_lead(current_org, lead_id)
    return current_org.db.select(
        "lead_notes",
        filters={"lead_id": f"eq.{lead_id}"},
        order="created_at.desc",
        limit=100,
    )


@router.get("/{lead_id}")
def get_lead(lead_id: str, current_org: OrgContext = Depends(get_current_org)):
    lead = _require_lead(current_org, lead_id)
    if "score_ia" in lead:
        lead["score"] = lead["score_ia"]
    try:
        lead["activities"] = current_org.db.select("activities", filters={"lead_id": f"eq.{lead_id}"}, order="created_at.desc", limit=50)
    except Exception:
        lead["activities"] = []
    try:
        lead["notas"] = current_org.db.select("lead_notes", filters={"lead_id": f"eq.{lead_id}"}, order="created_at.asc", limit=100)
    except Exception:
        lead["notas"] = []
    return lead


@router.patch("/{lead_id}")
@router.put("/{lead_id}")
def update_lead(request: Request, lead_id: str, body: LeadUpdate, current_org: OrgContext = Depends(get_current_org)):
    _require_lead(current_org, lead_id)
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    update_data["updated_at"] = datetime.utcnow().isoformat()
    update_data["ultima_actividad"] = datetime.utcnow().isoformat()
    updated = current_org.db.update("leads", lead_id, update_data)
    write_audit_log(org=current_org, action="lead.update", entity="lead", entity_id=lead_id, metadata={"fields": list(update_data.keys())}, request=request)
    return updated

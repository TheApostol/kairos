import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from services.supabase_client import db
from config import settings

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


# ─────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────

class CampaignCreate(BaseModel):
    nombre: str
    tipo: str  # "email" | "whatsapp" | "sms"
    asunto: Optional[str] = None
    cuerpo: str
    cuerpo_html: Optional[str] = None
    segmento: Optional[dict] = None


class GenerateTextRequest(BaseModel):
    tipo: str
    segmento_desc: str
    producto_destacado: Optional[str] = None


# ─────────────────────────────────────────────
# EMAIL SENDER (Brevo)
# ─────────────────────────────────────────────

def _send_email_brevo(to_email: str, to_name: str, subject: str, html_body: str, text_body: str) -> dict:
    import httpx

    if not settings.BREVO_API_KEY:
        return {"error": "BREVO_API_KEY not configured"}

    payload = {
        "sender": {"name": "Kairos CRM", "email": "noreply@kairos.com"},
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject,
        "htmlContent": html_body or f"<p>{text_body}</p>",
        "textContent": text_body,
    }

    with httpx.Client(timeout=15) as client:
        resp = client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": settings.BREVO_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code in (200, 201):
            return {"success": True, "message_id": resp.json().get("messageId")}
        return {"error": resp.text, "status_code": resp.status_code}


# ─────────────────────────────────────────────
# BACKGROUND TASK
# ─────────────────────────────────────────────

def _execute_campaign(campaign_id: str):
    campaigns = db.select("campaigns", filters={"id": f"eq.{campaign_id}"}, limit=1)
    if not campaigns:
        return

    campaign = campaigns[0]
    segmento = campaign.get("segmento") or {}

    # Build leads filter from segment
    params: dict = {"select": "*", "limit": 5000}
    if segmento.get("provincia"):
        params["provincia"] = f"ilike.%{segmento['provincia']}%"
    if segmento.get("estado"):
        params["estado"] = f"eq.{segmento['estado']}"
    if segmento.get("rubro"):
        params["rubro"] = f"ilike.%{segmento['rubro']}%"
    if segmento.get("score_min"):
        params["score_ia"] = f"gte.{segmento['score_min']}"
    if campaign.get("tipo") == "email":
        params["email"] = "neq."

    leads = db.raw_select("leads", params)
    total = len(leads)

    # Update campaign with total
    db.update("campaigns", campaign_id, {
        "estado": "enviando",
        "total_leads": total,
        "updated_at": datetime.utcnow().isoformat(),
    })

    enviados = 0
    errors = 0

    for lead in leads:
        email_dest = lead.get("email", "")
        send_record = {
            "campaign_id": campaign_id,
            "lead_id": lead.get("id"),
            "estado": "pendiente",
            "email_dest": email_dest,
            "created_at": datetime.utcnow().isoformat(),
        }

        if campaign.get("tipo") == "email" and email_dest:
            result = _send_email_brevo(
                to_email=email_dest,
                to_name=lead.get("empresa", ""),
                subject=campaign.get("asunto", ""),
                html_body=campaign.get("cuerpo_html", ""),
                text_body=campaign.get("cuerpo", ""),
            )
            if result.get("success"):
                send_record["estado"] = "enviado"
                send_record["enviado_at"] = datetime.utcnow().isoformat()
                enviados += 1
            else:
                send_record["estado"] = "error"
                send_record["error_msg"] = result.get("error", "Unknown error")[:500]
                errors += 1
        else:
            send_record["estado"] = "enviado"
            send_record["enviado_at"] = datetime.utcnow().isoformat()
            enviados += 1

        db.insert("campaign_sends", send_record)

    db.update("campaigns", campaign_id, {
        "estado": "completada",
        "enviados": enviados,
        "fecha_envio": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    })


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@router.get("/stats")
def get_campaigns_stats():
    campaigns = db.select("campaigns", limit=1000)
    total = len(campaigns)
    emails_enviados = sum(int(c.get("enviados") or 0) for c in campaigns)
    all_abiertos = [c for c in campaigns if (c.get("enviados") or 0) > 0]
    tasa_promedio = 0.0
    if all_abiertos:
        tasas = [100 * int(c.get("abiertos") or 0) / int(c.get("enviados") or 1) for c in all_abiertos]
        tasa_promedio = round(sum(tasas) / len(tasas), 1)
    conversiones = sum(int(c.get("convertidos") or 0) for c in campaigns)
    return {
        "total": total,
        "emails_enviados": emails_enviados,
        "tasa_apertura_promedio": tasa_promedio,
        "conversiones": conversiones,
    }


@router.get("")
def list_campaigns():
    campaigns = db.select("campaigns", order="created_at.desc", limit=100)
    return {"items": campaigns, "total": len(campaigns)}


@router.post("")
def create_campaign(body: CampaignCreate):
    data = {
        "nombre": body.nombre,
        "tipo": body.tipo,
        "estado": "borrador",
        "asunto": body.asunto,
        "cuerpo": body.cuerpo,
        "cuerpo_html": body.cuerpo_html,
        "segmento": body.segmento,
        "total_leads": 0,
        "enviados": 0,
        "abiertos": 0,
        "clicks": 0,
        "respondidos": 0,
        "convertidos": 0,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    campaign = db.insert("campaigns", data)
    return campaign


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str):
    campaigns = db.select("campaigns", filters={"id": f"eq.{campaign_id}"}, limit=1)
    if not campaigns:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign = campaigns[0]

    sends = db.select(
        "campaign_sends",
        filters={"campaign_id": f"eq.{campaign_id}"},
        order="created_at.desc",
        limit=200,
    )
    campaign["sends"] = sends
    return campaign


@router.post("/{campaign_id}/send")
def send_campaign(campaign_id: str, background_tasks: BackgroundTasks):
    campaigns = db.select("campaigns", filters={"id": f"eq.{campaign_id}"}, limit=1)
    if not campaigns:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign = campaigns[0]
    if campaign.get("estado") == "completada":
        raise HTTPException(status_code=400, detail="Campaign already sent")

    background_tasks.add_task(_execute_campaign, campaign_id)

    db.update("campaigns", campaign_id, {
        "estado": "programada",
        "updated_at": datetime.utcnow().isoformat(),
    })

    return {"message": "Campaign send started", "campaign_id": campaign_id}


@router.get("/{campaign_id}/analytics")
def get_campaign_analytics(campaign_id: str):
    campaigns = db.select("campaigns", filters={"id": f"eq.{campaign_id}"}, limit=1)
    if not campaigns:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign = campaigns[0]

    sends = db.raw_select("campaign_sends", {
        "select": "*",
        "campaign_id": f"eq.{campaign_id}",
        "limit": 5000,
    })

    total = len(sends)
    by_estado: dict = {}
    for s in sends:
        estado = s.get("estado", "unknown")
        by_estado[estado] = by_estado.get(estado, 0) + 1

    enviados = campaign.get("enviados") or 0
    abiertos = campaign.get("abiertos") or 0
    clicks = campaign.get("clicks") or 0
    respondidos = campaign.get("respondidos") or 0
    convertidos = campaign.get("convertidos") or 0

    def pct(num, denom):
        if denom == 0:
            return 0.0
        return round(100 * num / denom, 2)

    return {
        "campaign_id": campaign_id,
        "nombre": campaign.get("nombre"),
        "estado": campaign.get("estado"),
        "total_leads": campaign.get("total_leads", 0),
        "enviados": enviados,
        "abiertos": abiertos,
        "clicks": clicks,
        "respondidos": respondidos,
        "convertidos": convertidos,
        "tasa_apertura": pct(abiertos, enviados),
        "tasa_clicks": pct(clicks, enviados),
        "tasa_respuesta": pct(respondidos, enviados),
        "tasa_conversion": pct(convertidos, enviados),
        "sends_by_estado": by_estado,
        "sends_total": total,
    }


@router.post("/generate-text")
def generate_campaign_text(body: GenerateTextRequest):
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured")

    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    producto_info = ""
    if body.producto_destacado:
        producto_info = f"\nProducto/servicio destacado: {body.producto_destacado}"

    prompt = f"""Eres un experto en marketing y ventas B2B para una empresa Argentina llamada Kairos.
Genera contenido de campaña {body.tipo} para el siguiente segmento de clientes:

Segmento: {body.segmento_desc}{producto_info}

Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura (sin markdown, sin texto extra):
{{
  "asunto": "Asunto del email (máximo 60 caracteres)",
  "cuerpo": "Texto plano del mensaje (2-3 párrafos, tono profesional pero cercano, en español argentino)",
  "cuerpo_html": "Versión HTML del cuerpo con formato básico (párrafos, negrita para puntos clave)",
  "followup_1": "Mensaje de seguimiento a los 3 días si no hubo respuesta",
  "followup_2": "Mensaje de seguimiento a los 7 días, más directo y con llamada a la acción clara"
}}

Consideraciones:
- Usa tuteo o voseo argentino según corresponda al segmento
- Incluí nombre de empresa como {{{{empresa}}}} como placeholder
- El tono debe ser profesional pero cálido, no agresivo
- Enfocate en valor y beneficios concretos
- Máximo 150 palabras por mensaje principal"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = message.content[0].text.strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {
                "asunto": "Propuesta especial para tu negocio",
                "cuerpo": raw_text,
                "cuerpo_html": f"<p>{raw_text}</p>",
                "followup_1": "",
                "followup_2": "",
            }

    return result

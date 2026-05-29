import asyncio
import re
import time
import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.supabase_client import db
from config import settings

router = APIRouter(prefix="/scraper", tags=["scraper"])


class ScraperStartRequest(BaseModel):
    queries: Optional[List[str]] = None
    google_api_key: Optional[str] = None
    max_per_query: int = 60


class EnrichRequest(BaseModel):
    lead_ids: Optional[List[str]] = None  # if None, enrich all without email


# ─────────────────────────────────────────────
# GOOGLE PLACES HELPERS (inline from scraper_holistica.py)
# ─────────────────────────────────────────────

DEFAULT_QUERIES = [
    "sahumerios Argentina",
    "tienda holistica Argentina",
    "santeria Argentina",
    "aromaterapia tienda Argentina",
    "velas de soja tienda Argentina",
    "esencias aromáticas tienda Argentina",
    "inciensos tienda Argentina",
    "productos esotericos tienda Argentina",
    "reiki shop Argentina",
    "tienda espiritual Argentina",
    "sahumerios Buenos Aires",
    "sahumerios Córdoba",
    "sahumerios Rosario",
    "sahumerios Mendoza",
    "tienda holistica Tucumán",
    "tienda holistica Salta",
    "tienda holistica Mar del Plata",
    "tienda holistica La Plata",
    "tienda esoterica Neuquén",
    "tienda esoterica Santa Fe",
]


def _places_text_search(api_key: str, query: str, page_token: Optional[str] = None) -> dict:
    import httpx
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": query,
        "key": api_key,
        "language": "es",
        "region": "ar",
    }
    if page_token:
        params["pagetoken"] = page_token

    with httpx.Client(timeout=15) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _place_details(api_key: str, place_id: str) -> dict:
    import httpx
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "key": api_key,
        "fields": "name,formatted_address,formatted_phone_number,international_phone_number,website,rating,user_ratings_total,price_level,opening_hours,address_components,url",
        "language": "es",
    }
    with httpx.Client(timeout=15) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json().get("result", {})


def _extract_province(address_components: list) -> str:
    for comp in address_components:
        if "administrative_area_level_1" in comp.get("types", []):
            return comp.get("long_name", "")
    return ""


def _extract_city(address_components: list) -> str:
    for comp in address_components:
        if "locality" in comp.get("types", []):
            return comp.get("long_name", "")
    return ""


def _infer_instagram(name: str, website: str = "") -> str:
    if website and "instagram.com" in website:
        return website
    slug = re.sub(r"[^a-z0-9]", "", name.lower().replace(" ", ""))
    return f"@{slug[:20]}"


def _score_lead(record: dict) -> int:
    score = 0
    if record.get("telefono"):
        score += 2
    if record.get("website"):
        score += 2
    if record.get("email"):
        score += 2
    if record.get("instagram"):
        score += 1
    rating = record.get("rating", 0)
    try:
        if rating and float(rating) >= 4.0:
            score += 2
    except (ValueError, TypeError):
        pass
    reviews = record.get("reviews_count", 0)
    try:
        if reviews and int(reviews) >= 20:
            score += 1
    except (ValueError, TypeError):
        pass
    return min(score, 10)


# ─────────────────────────────────────────────
# ENRICHMENT HELPERS (inline from enriquecedor.py)
# ─────────────────────────────────────────────

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
INSTAGRAM_REGEX = re.compile(r"instagram\.com/([A-Za-z0-9._]{1,30})")
WA_REGEX = re.compile(r"(?:wa\.me|whatsapp\.com/send\?phone=)[/\?]?(\d{6,15})")

_ENRICH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def _scrape_website(url: str) -> dict:
    import httpx
    try:
        from bs4 import BeautifulSoup
        bs4_available = True
    except ImportError:
        bs4_available = False

    result = {"email": "", "instagram": "", "whatsapp": ""}
    if not url or not url.startswith("http"):
        return result

    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            resp = client.get(url, headers=_ENRICH_HEADERS)
            if resp.status_code != 200:
                return result

        text = resp.text

        emails = EMAIL_REGEX.findall(text)
        valid_emails = [
            e for e in emails
            if not any(x in e for x in ["example", "domain", "sentry", "wix", "shopify"])
        ]
        if valid_emails:
            result["email"] = valid_emails[0]

        ig_matches = INSTAGRAM_REGEX.findall(text)
        if ig_matches:
            result["instagram"] = f"@{ig_matches[0]}"

        wa_matches = WA_REGEX.findall(text)
        if wa_matches:
            result["whatsapp"] = wa_matches[0]

        if bs4_available:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "instagram.com" in href and not result["instagram"]:
                    ig = INSTAGRAM_REGEX.search(href)
                    if ig:
                        result["instagram"] = f"@{ig.group(1)}"
                if "wa.me" in href and not result["whatsapp"]:
                    wa = WA_REGEX.search(href)
                    if wa:
                        result["whatsapp"] = wa.group(1)
                if "mailto:" in href and not result["email"]:
                    result["email"] = href.replace("mailto:", "").split("?")[0]

    except Exception:
        pass

    return result


# ─────────────────────────────────────────────
# BACKGROUND TASKS
# ─────────────────────────────────────────────

def _run_scraper_job(job_id: str, queries: List[str], api_key: str, max_per_query: int):
    seen_ids: set = set()
    results = []
    total_queries = len(queries)

    try:
        db.update("scraper_jobs", job_id, {
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "total": total_queries,
            "progress": 0,
        })

        for i, query in enumerate(queries):
            next_page_token = None
            page = 0

            while page < 3:
                try:
                    if page > 0 and next_page_token:
                        time.sleep(2)

                    data = _places_text_search(api_key, query, next_page_token)
                    places = data.get("results", [])

                    for place in places:
                        pid = place.get("place_id")
                        if pid in seen_ids:
                            continue
                        seen_ids.add(pid)

                        time.sleep(0.1)
                        details = _place_details(api_key, pid)

                        addr_comps = details.get("address_components", [])
                        phone = details.get("formatted_phone_number", "") or details.get(
                            "international_phone_number", ""
                        )
                        website = details.get("website", "")

                        record = {
                            "empresa": details.get("name", place.get("name", "")),
                            "rubro": "Tienda Holística / Sahumerios",
                            "direccion": details.get("formatted_address", ""),
                            "ciudad": _extract_city(addr_comps),
                            "provincia": _extract_province(addr_comps),
                            "telefono": phone,
                            "website": website,
                            "google_maps_url": details.get("url", ""),
                            "rating": details.get("rating"),
                            "reviews_count": details.get("user_ratings_total"),
                            "price_level": details.get("price_level"),
                            "horarios": "; ".join(
                                details.get("opening_hours", {}).get("weekday_text", [])
                            ),
                            "instagram": _infer_instagram(place.get("name", ""), website),
                            "email": "",
                            "whatsapp": phone.replace(" ", "").replace("-", "").replace("+", "")
                            if phone
                            else "",
                            "observaciones": "",
                            "fuente": "Google Places API",
                            "fecha_extraccion": datetime.utcnow().date().isoformat(),
                            "estado": "nuevo",
                        }
                        record["score_ia"] = _score_lead(record)

                        try:
                            existing = db.select(
                                "leads",
                                filters={"empresa": f"eq.{record['empresa']}"},
                                limit=1,
                            )
                            if not existing:
                                db.insert("leads", record)
                                results.append(record)
                        except Exception:
                            results.append(record)

                    next_page_token = data.get("next_page_token")
                    if not next_page_token:
                        break
                    page += 1

                except Exception:
                    break

            time.sleep(0.5)

            progress = int(((i + 1) / total_queries) * 100)
            db.update("scraper_jobs", job_id, {
                "progress": progress,
                "new_found": len(results),
                "total_found": len(seen_ids),
            })

        db.update("scraper_jobs", job_id, {
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "progress": 100,
            "new_found": len(results),
            "total_found": len(seen_ids),
        })

    except Exception as exc:
        db.update("scraper_jobs", job_id, {
            "status": "failed",
            "error_msg": str(exc),
            "completed_at": datetime.utcnow().isoformat(),
        })


def _run_enrichment_job(job_id: str, lead_ids: Optional[List[str]]):
    try:
        db.update("scraper_jobs", job_id, {
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
        })

        params = {"select": "*", "website": "neq.", "email": "eq.", "limit": 500}
        if lead_ids:
            ids_str = ",".join(lead_ids)
            params = {"select": "*", "id": f"in.({ids_str})", "limit": len(lead_ids)}

        leads = db.raw_select("leads", params)
        total = len(leads)
        enriched_count = 0

        db.update("scraper_jobs", job_id, {"total": total})

        for i, lead in enumerate(leads):
            website = lead.get("website", "")
            if not website:
                continue

            enrich = _scrape_website(website)
            update_data = {}

            for field in ["email", "instagram", "whatsapp"]:
                if enrich.get(field) and not lead.get(field):
                    update_data[field] = enrich[field]

            if update_data:
                update_data["updated_at"] = datetime.utcnow().isoformat()
                db.update("leads", lead["id"], update_data)
                enriched_count += 1

            time.sleep(0.3)
            progress = int(((i + 1) / max(total, 1)) * 100)
            db.update("scraper_jobs", job_id, {
                "progress": progress,
                "new_found": enriched_count,
            })

        db.update("scraper_jobs", job_id, {
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "progress": 100,
            "new_found": enriched_count,
            "total_found": total,
        })

    except Exception as exc:
        db.update("scraper_jobs", job_id, {
            "status": "failed",
            "error_msg": str(exc),
            "completed_at": datetime.utcnow().isoformat(),
        })


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@router.post("/start")
def start_scraper(body: ScraperStartRequest, background_tasks: BackgroundTasks):
    api_key = body.google_api_key or settings.GOOGLE_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Google API key required. Pass google_api_key in the request body or set GOOGLE_API_KEY env var.",
        )

    queries = body.queries or DEFAULT_QUERIES

    job = db.insert("scraper_jobs", {
        "status": "pending",
        "queries": queries,
        "progress": 0,
        "total": len(queries),
        "new_found": 0,
        "total_found": 0,
        "created_at": datetime.utcnow().isoformat(),
    })

    job_id = job.get("id") or job.get("id")
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to create scraper job")

    background_tasks.add_task(_run_scraper_job, str(job_id), queries, api_key, body.max_per_query)

    return {"job_id": job_id, "status": "pending", "queries_count": len(queries)}


@router.get("/jobs")
def list_jobs():
    jobs = db.select("scraper_jobs", order="created_at.desc", limit=20)
    return {"data": jobs}


@router.get("/stream/{job_id}")
async def stream_job_progress(job_id: str):
    async def event_generator():
        while True:
            jobs = db.select("scraper_jobs", filters={"id": f"eq.{job_id}"}, limit=1)
            if not jobs:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                return

            job = jobs[0]
            payload = {
                "job_id": job_id,
                "status": job.get("status"),
                "progress": job.get("progress", 0),
                "total_found": job.get("total_found", 0),
                "new_found": job.get("new_found", 0),
                "error_msg": job.get("error_msg"),
            }
            yield f"data: {json.dumps(payload)}\n\n"

            status = job.get("status")
            if status in ("completed", "failed"):
                return

            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/enrich")
def start_enrichment(body: EnrichRequest, background_tasks: BackgroundTasks):
    job = db.insert("scraper_jobs", {
        "status": "pending",
        "queries": ["enrichment"],
        "progress": 0,
        "new_found": 0,
        "total_found": 0,
        "created_at": datetime.utcnow().isoformat(),
    })

    job_id = job.get("id")
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to create enrichment job")

    background_tasks.add_task(_run_enrichment_job, str(job_id), body.lead_ids)

    return {"job_id": job_id, "status": "pending"}

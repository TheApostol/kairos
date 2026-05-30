import asyncio
import gc
import re
import time
import json
from datetime import datetime, timezone
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
    tipo_cliente: str = "lead"  # "lead" or "mayorista"


class EnrichRequest(BaseModel):
    lead_ids: Optional[List[str]] = None  # if None, enrich all without email


# ─────────────────────────────────────────────
# GOOGLE PLACES HELPERS (inline from scraper_holistica.py)
# ─────────────────────────────────────────────

IRRELEVANT_PLACE_TYPES = {
    "gym", "fitness_center", "restaurant", "food", "bar", "cafe", "bakery",
    "meal_takeaway", "meal_delivery", "supermarket", "grocery_or_supermarket",
    "lodging", "hotel", "car_repair", "car_dealer", "car_wash", "gas_station",
    "bank", "atm", "school", "university", "hospital", "doctor", "dentist",
    "pharmacy", "veterinary_care", "hair_care", "beauty_salon", "spa",
    "laundry", "accounting", "lawyer", "insurance_agency", "real_estate_agency",
    "night_club", "movie_theater", "bowling_alley", "stadium",
}

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

MAYORISTA_QUERIES = [
    "distribuidor sahumerios Argentina",
    "mayorista productos holísticos Argentina",
    "distribuidor inciensos Argentina",
    "mayorista velas aromaticas Argentina",
    "distribuidor esencias aromáticas Argentina",
    "importador sahumerios Argentina",
    "mayorista productos esotéricos Argentina",
    "distribuidor chakras aromaterapia Argentina",
    "mayorista incienso sándalo nag champa Argentina",
    "distribuidor tiendas espirituales Argentina",
    "mayorista sahumerios Buenos Aires",
    "distribuidor holístico Córdoba",
    "mayorista aromaterapia Rosario",
    "importador velas soja Argentina",
    "distribuidor products naturales holísticos Argentina",
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
# Broad Argentina phone pattern: captures 8-15 digit sequences from tel: links and text
TEL_HREF_REGEX = re.compile(r'href=["\']tel:([+\d\s\-().]{6,20})["\']', re.IGNORECASE)
# Phone pattern in plain text: handles formats like (011) 4567-8901, 011-15-1234-5678, +54 9 11 etc.
PHONE_TEXT_REGEX = re.compile(
    r'(?<!\d)'
    r'(?:\+54[\s\-]?)?'
    r'(?:0?11|0?[2-9]\d{1,3})?'
    r'[\s\-]?'
    r'(?:15[\s\-]?)?'
    r'\d{4}[\s\-]?\d{4}'
    r'(?!\d)'
)

_ENRICH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

FAKE_EMAIL_FRAGMENTS = [
    "noreply", "no-reply", "example", "domain.com", "sentry", "wix.com", "shopify",
    "wordpress", "your@", "test@", "info@example", "@sentry", "yourdomain",
    "schema.org", "w3.org", "placeholder",
]


def _is_valid_email(email: str) -> bool:
    e = email.lower()
    return (
        "@" in e
        and "." in e.split("@")[-1]
        and not any(x in e for x in FAKE_EMAIL_FRAGMENTS)
        and len(e) >= 6
    )


def _extract_from_soup(soup, result: dict) -> None:
    """Extract contact info using BeautifulSoup from parsed HTML."""
    from bs4 import BeautifulSoup  # already imported by caller

    # 1. JSON-LD schema.org — most reliable source
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                data = data[0]
            if not result["email"] and data.get("email"):
                candidate = str(data["email"]).strip()
                if _is_valid_email(candidate):
                    result["email"] = candidate
            if not result["telefono"] and data.get("telephone"):
                result["telefono"] = str(data["telephone"]).strip()
        except Exception:
            pass

    # 2. Microdata: itemprop attributes
    for el in soup.find_all(itemprop=True):
        prop = el.get("itemprop", "")
        if prop == "email" and not result["email"]:
            candidate = el.get("content") or el.get_text(strip=True)
            if candidate and _is_valid_email(candidate):
                result["email"] = candidate
        if prop == "telephone" and not result["telefono"]:
            val = el.get("content") or el.get_text(strip=True)
            if val:
                result["telefono"] = val.strip()

    # 3. All <a> tags — mailto, tel, instagram, whatsapp
    for a in soup.find_all("a", href=True):
        href = str(a.get("href", ""))
        if "mailto:" in href and not result["email"]:
            candidate = href.split("mailto:")[-1].split("?")[0].strip()
            if _is_valid_email(candidate):
                result["email"] = candidate
        if href.startswith("tel:") and not result["telefono"]:
            raw = href[4:].strip().replace(" ", "").replace("-", "")
            if raw:
                result["telefono"] = href[4:].strip()
        if "instagram.com" in href and not result["instagram"]:
            ig = INSTAGRAM_REGEX.search(href)
            if ig and ig.group(1) not in ("p", "reel", "stories", "explore", "accounts"):
                result["instagram"] = f"@{ig.group(1)}"
        if ("wa.me" in href or "whatsapp.com" in href) and not result["whatsapp"]:
            wa = WA_REGEX.search(href)
            if wa:
                result["whatsapp"] = wa.group(1)

    # 4. Focus on footer / contact-section text for email if still missing
    if not result["email"]:
        priority_zones = (
            soup.find_all("footer")
            + soup.find_all(class_=re.compile(r"footer|contact|contacto|pie|bottom", re.I))
            + soup.find_all(id=re.compile(r"footer|contact|contacto|pie|bottom", re.I))
        )
        for zone in priority_zones:
            emails = EMAIL_REGEX.findall(zone.get_text())
            valid = [e for e in emails if _is_valid_email(e)]
            if valid:
                result["email"] = valid[0]
                break

    # 5. Fallback: scan all text for phone if still missing
    if not result["telefono"]:
        tel_matches = TEL_HREF_REGEX.findall(str(soup))
        if tel_matches:
            result["telefono"] = tel_matches[0].strip()


def _scrape_website(url: str) -> dict:
    import httpx
    try:
        from bs4 import BeautifulSoup
        bs4_available = True
    except ImportError:
        bs4_available = False

    result = {"email": "", "instagram": "", "whatsapp": "", "telefono": ""}
    if not url or not url.startswith("http"):
        return result

    base_url = url.rstrip("/")
    pages_to_try = [
        base_url,
        base_url + "/contacto",
        base_url + "/contactanos",
        base_url + "/contact",
        base_url + "/sobre-nosotros",
    ]

    MAX_BODY_BYTES = 400_000  # 400KB cap to avoid OOM on Render free tier

    try:
        with httpx.Client(timeout=12, follow_redirects=True) as client:
            for page_url in pages_to_try:
                try:
                    resp = client.get(page_url, headers=_ENRICH_HEADERS)
                    if resp.status_code != 200:
                        continue

                    # Read only up to MAX_BODY_BYTES to avoid loading multi-MB pages
                    raw = resp.content[:MAX_BODY_BYTES]
                    text = raw.decode("utf-8", errors="replace")
                    del raw

                    if bs4_available:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(text, "html.parser")
                        _extract_from_soup(soup, result)
                        soup.decompose()
                        del soup
                    else:
                        # Fallback regex-only path
                        if not result["email"]:
                            emails = EMAIL_REGEX.findall(text)
                            valid = [e for e in emails if _is_valid_email(e)]
                            if valid:
                                result["email"] = valid[0]
                        if not result["instagram"]:
                            ig_m = INSTAGRAM_REGEX.findall(text)
                            if ig_m:
                                result["instagram"] = f"@{ig_m[0]}"
                        if not result["whatsapp"]:
                            wa_m = WA_REGEX.findall(text)
                            if wa_m:
                                result["whatsapp"] = wa_m[0]
                        if not result["telefono"]:
                            tel_m = TEL_HREF_REGEX.findall(text)
                            if tel_m:
                                result["telefono"] = tel_m[0].strip()

                    if result["email"] and result["telefono"]:
                        break

                except Exception:
                    continue

    except Exception:
        pass

    return result


# ─────────────────────────────────────────────
# BACKGROUND TASKS
# ─────────────────────────────────────────────

def _run_scraper_job(job_id: str, queries: List[str], api_key: str, max_per_query: int, tipo_cliente: str = "lead"):
    seen_ids: set = set()
    results = []
    total_queries = len(queries)

    try:
        db.update("scraper_jobs", job_id, {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
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

                        place_types = set(place.get("types", []))
                        if place_types & IRRELEVANT_PLACE_TYPES:
                            continue

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
                            "fecha_extraccion": datetime.now(timezone.utc).date().isoformat(),
                            "estado": "nuevo",
                            "tipo_cliente": tipo_cliente,
                        }
                        record["score_ia"] = _score_lead(record)

                        try:
                            existing = db.select(
                                "leads",
                                filters={
                                    "empresa": f"eq.{record['empresa']}",
                                    "tipo_cliente": f"eq.{tipo_cliente}",
                                },
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
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress": 100,
            "new_found": len(results),
            "total_found": len(seen_ids),
        })

    except Exception as exc:
        db.update("scraper_jobs", job_id, {
            "status": "failed",
            "error_msg": str(exc),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })


def _run_enrichment_job(job_id: str, lead_ids: Optional[List[str]]):
    try:
        db.update("scraper_jobs", job_id, {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

        BATCH_SIZE = 200  # process in chunks to keep memory low on Render free tier

        if lead_ids:
            ids_str = ",".join(lead_ids)
            all_leads = db.raw_select("leads", {"select": "*", "id": f"in.({ids_str})", "limit": len(lead_ids)})
        else:
            all_leads = db.raw_select("leads", {"select": "*", "website": "neq.", "limit": BATCH_SIZE})
            all_leads = [l for l in all_leads if not l.get("email")]

        total = len(all_leads)
        enriched_count = 0

        db.update("scraper_jobs", job_id, {"total": total})

        for i, lead in enumerate(all_leads):
            website = lead.get("website", "")
            if not website:
                continue

            enrich = _scrape_website(website)
            update_data = {}

            for field in ["email", "instagram", "whatsapp", "telefono"]:
                if enrich.get(field) and not lead.get(field):
                    update_data[field] = enrich[field]

            if update_data:
                merged = {**lead, **update_data}
                update_data["score_ia"] = _score_lead(merged)
                update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                db.update("leads", lead["id"], update_data)
                enriched_count += 1

            del enrich, update_data

            # Run GC every 25 leads to reclaim BS4 / httpx memory
            if (i + 1) % 25 == 0:
                gc.collect()

            time.sleep(0.3)
            progress = int(((i + 1) / max(total, 1)) * 100)
            db.update("scraper_jobs", job_id, {
                "progress": progress,
                "new_found": enriched_count,
            })

        del all_leads
        gc.collect()

        db.update("scraper_jobs", job_id, {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress": 100,
            "new_found": enriched_count,
            "total_found": total,
        })

    except Exception as exc:
        db.update("scraper_jobs", job_id, {
            "status": "failed",
            "error_msg": str(exc),
            "completed_at": datetime.now(timezone.utc).isoformat(),
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

    # Prevent duplicate concurrent jobs
    active = db.raw_select("scraper_jobs", {"select": "id,status", "status": "in.(pending,running)", "limit": 1})
    if active:
        raise HTTPException(status_code=409, detail="Ya hay un job corriendo. Esperá a que termine antes de iniciar otro.")

    tipo_cliente = body.tipo_cliente or "lead"
    if body.queries:
        queries = body.queries
    elif tipo_cliente == "mayorista":
        queries = MAYORISTA_QUERIES
    else:
        queries = DEFAULT_QUERIES

    job = db.insert("scraper_jobs", {
        "status": "pending",
        "queries": queries,
        "progress": 0,
        "total": len(queries),
        "new_found": 0,
        "total_found": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    job_id = job.get("id")
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to create scraper job")

    background_tasks.add_task(_run_scraper_job, str(job_id), queries, api_key, body.max_per_query, tipo_cliente)

    return {"job_id": job_id, "status": "pending", "queries_count": len(queries), "tipo_cliente": tipo_cliente}


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


@router.post("/run")
def run_scraper(body: ScraperStartRequest, background_tasks: BackgroundTasks):
    """Alias for /start — used by the frontend."""
    return start_scraper(body, background_tasks)


@router.get("/history")
def get_history():
    """Frontend-compatible alias for /jobs with mapped field names."""
    jobs = db.select("scraper_jobs", order="created_at.desc", limit=20)
    status_map = {"completed": "completado", "failed": "error", "running": "corriendo", "pending": "pendiente"}
    items = [
        {
            "id": job.get("id"),
            "started_at": job.get("started_at"),
            "finished_at": job.get("completed_at"),
            "estado": status_map.get(job.get("status", ""), job.get("status", "pendiente")),
            "total_encontrados": job.get("total_found"),
            "nuevos_agregados": job.get("new_found"),
            "error": job.get("error_msg"),
            "progress": job.get("progress", 0),
            "total": job.get("total", 0),
            "tipo": "enrichment" if job.get("queries") == ["enrichment"] else "scraper",
        }
        for job in jobs
    ]
    return {"items": items}


@router.get("/progress")
async def stream_latest_progress():
    """SSE stream for the most recent job — used by the frontend."""
    async def event_generator():
        while True:
            jobs = db.select("scraper_jobs", order="created_at.desc", limit=1)
            if not jobs:
                yield f"data: {json.dumps({'done': True, 'progress': 0})}\n\n"
                return

            job = jobs[0]
            status = job.get("status", "")
            progress = job.get("progress", 0)

            payload: dict = {
                "progress": progress,
                "total_found": job.get("total_found", 0),
                "new_found": job.get("new_found", 0),
                "done": status in ("completed", "failed"),
            }
            if status == "failed":
                payload["error"] = job.get("error_msg", "Error desconocido")

            yield f"data: {json.dumps(payload)}\n\n"

            if status in ("completed", "failed"):
                return

            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/enrich")
def start_enrichment(body: EnrichRequest, background_tasks: BackgroundTasks):
    # Prevent duplicate concurrent jobs
    active = db.raw_select("scraper_jobs", {"select": "id,status", "status": "in.(pending,running)", "limit": 1})
    if active:
        raise HTTPException(status_code=409, detail="Ya hay un job corriendo. Esperá a que termine antes de iniciar otro.")

    job = db.insert("scraper_jobs", {
        "status": "pending",
        "queries": ["enrichment"],
        "progress": 0,
        "new_found": 0,
        "total_found": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    job_id = job.get("id")
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to create enrichment job")

    background_tasks.add_task(_run_enrichment_job, str(job_id), body.lead_ids)

    return {"job_id": job_id, "status": "pending"}

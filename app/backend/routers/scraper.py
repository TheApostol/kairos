import asyncio
import gc
import logging
import re
import time
import json
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.auth import OrgContext, get_current_org
from services.supabase_client import db, ScopedSupabaseClient
from services.scraping_utils import discover_website_ddg
from sources import SOURCE_REGISTRY, DEFAULT_SOURCES
from sources.google_places import DEFAULT_QUERIES, MAYORISTA_QUERIES, PlacesAPIError
from config import settings

router = APIRouter(prefix="/scraper", tags=["scraper"])

logger = logging.getLogger(__name__)


class ScraperStartRequest(BaseModel):
    queries: Optional[List[str]] = None
    google_api_key: Optional[str] = None
    max_per_query: int = 60
    tipo_cliente: str = "lead"  # "lead" or "mayorista"
    sources: Optional[List[str]] = None
    source_options: Optional[dict] = None


class EnrichRequest(BaseModel):
    lead_ids: Optional[List[str]] = None  # if None, enrich all without email


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


def _decode_cloudflare_email(encoded: str) -> str:
    try:
        key = int(encoded[:2], 16)
        return "".join(chr(int(encoded[i:i+2], 16) ^ key) for i in range(2, len(encoded), 2))
    except Exception:
        return ""


def _extract_from_soup(soup, result: dict) -> None:
    """Extract contact info using BeautifulSoup from parsed HTML."""

    # 0. Cloudflare email protection (data-cfemail XOR encoding)
    for el in soup.find_all(attrs={"data-cfemail": True}):
        if not result["email"]:
            decoded = _decode_cloudflare_email(el["data-cfemail"])
            if decoded and _is_valid_email(decoded):
                result["email"] = decoded

    # 1. JSON-LD schema.org — most reliable source (handles nested contactPoint too)
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
            # Handle @graph arrays and plain lists
            entries = []
            if isinstance(data, list):
                entries = data
            elif isinstance(data, dict):
                entries = data.get("@graph", [data])
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                # direct email/telephone
                if not result["email"] and entry.get("email"):
                    c = str(entry["email"]).strip()
                    if _is_valid_email(c):
                        result["email"] = c
                if not result["telefono"] and entry.get("telephone"):
                    result["telefono"] = str(entry["telephone"]).strip()
                # nested contactPoint
                cp = entry.get("contactPoint") or {}
                if isinstance(cp, list):
                    cp = cp[0] if cp else {}
                if not result["email"] and cp.get("email"):
                    c = str(cp["email"]).strip()
                    if _is_valid_email(c):
                        result["email"] = c
                if not result["telefono"] and cp.get("telephone"):
                    result["telefono"] = str(cp["telephone"]).strip()
        except Exception:
            pass

    # 2. <meta> tags (some themes put email in og:email or similar)
    for meta in soup.find_all("meta"):
        content = meta.get("content", "")
        name = (meta.get("name") or meta.get("property") or "").lower()
        if not result["email"] and ("email" in name or "mail" in name):
            if content and _is_valid_email(content):
                result["email"] = content
        # data-email attribute anywhere
    for el in soup.find_all(attrs={"data-email": True}):
        if not result["email"]:
            c = el["data-email"].strip()
            if _is_valid_email(c):
                result["email"] = c

    # 3. Microdata: itemprop attributes
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

    # 3b. CSS class/ID scan for email and phone containers
    if not result["email"]:
        for el in soup.find_all(class_=re.compile(r'\b(e-?mail|correo|contacto?)\b', re.I)):
            emails = EMAIL_REGEX.findall(el.get_text(" "))
            valid = [e for e in emails if _is_valid_email(e)]
            if valid:
                result["email"] = valid[0]
                break

    if not result["telefono"]:
        for el in soup.find_all(class_=re.compile(r'\b(tel[eé]?fono?|phone|cel(ular)?|whatsapp)\b', re.I)):
            m = PHONE_TEXT_REGEX.search(el.get_text(" "))
            if m and len(re.sub(r'\D', '', m.group())) >= 8:
                result["telefono"] = m.group().strip()
                break

    # 4. All <a> tags — mailto, tel, instagram, whatsapp
    for a in soup.find_all("a", href=True):
        href = str(a.get("href", ""))
        if "mailto:" in href and not result["email"]:
            candidate = href.split("mailto:")[-1].split("?")[0].strip()
            if _is_valid_email(candidate):
                result["email"] = candidate
        if href.startswith("tel:") and not result["telefono"]:
            raw = href[4:].strip()
            if raw:
                result["telefono"] = raw
        if "instagram.com" in href and not result["instagram"]:
            ig = INSTAGRAM_REGEX.search(href)
            if ig and ig.group(1) not in ("p", "reel", "stories", "explore", "accounts"):
                result["instagram"] = f"@{ig.group(1)}"
        if ("wa.me" in href or "whatsapp.com" in href) and not result["whatsapp"]:
            wa = WA_REGEX.search(href)
            if wa:
                result["whatsapp"] = wa.group(1)
                if not result["telefono"]:
                    result["telefono"] = "+" + wa.group(1)

    # 5. Priority zones: footer / contact sections
    if not result["email"] or not result["telefono"]:
        priority_zones = (
            soup.find_all("footer")
            + soup.find_all(class_=re.compile(r"footer|cont[aá]ct|contacto|contáctenos|pie|bottom|sidebar", re.I))
            + soup.find_all(id=re.compile(r"footer|cont[aá]ct|contacto|contáctenos|pie|bottom|sidebar", re.I))
        )
        for zone in priority_zones:
            zone_text = zone.get_text(" ")
            if not result["email"]:
                emails = EMAIL_REGEX.findall(zone_text)
                valid = [e for e in emails if _is_valid_email(e)]
                if valid:
                    result["email"] = valid[0]
            if not result["telefono"]:
                m = PHONE_TEXT_REGEX.search(zone_text)
                if m and len(re.sub(r'\D', '', m.group())) >= 8:
                    result["telefono"] = m.group().strip()
            if result["email"] and result["telefono"]:
                break

    # 5c. Heading-based "Contáctenos" / "Contacto" section scanner
    if not result["email"] or not result["telefono"]:
        for heading in soup.find_all(['h1','h2','h3','h4','h5','h6','p','span'],
                                      string=re.compile(r'cont[aá]ct', re.I)):
            parent = heading.find_parent(['section', 'div', 'article', 'footer', 'aside'])
            if not parent:
                continue
            parent_text = parent.get_text(" ")
            if not result["email"]:
                emails = EMAIL_REGEX.findall(parent_text)
                valid = [e for e in emails if _is_valid_email(e)]
                if valid:
                    result["email"] = valid[0]
            if not result["telefono"]:
                m = PHONE_TEXT_REGEX.search(parent_text)
                if m and len(re.sub(r'\D', '', m.group())) >= 8:
                    result["telefono"] = m.group().strip()
            if result["email"] and result["telefono"]:
                break

    # 5b. Phone-prefix label scan: "Tel:", "Cel:", "WhatsApp:" in plain elements
    if not result["telefono"]:
        for el in soup.find_all(['p', 'li', 'span', 'div']):
            txt = el.get_text(" ", strip=True)
            if re.search(r'\b(tel[eé]?[f.]?|cel(ular)?|whatsapp|fax)\s*[:\-]', txt, re.I):
                m = PHONE_TEXT_REGEX.search(txt)
                if m and len(re.sub(r'\D', '', m.group())) >= 8:
                    result["telefono"] = m.group().strip()
                    break

    # 6. FULL page text scan — last resort, catches plain-text emails in any element
    if not result["email"]:
        full_text = soup.get_text(separator=" ")
        # Also try deobfuscated forms: "info [at] empresa.com", "info(at)empresa.com"
        deob = re.sub(r'\s*\[at\]\s*|\s*\(at\)\s*|\s+AT\s+|\{at\}|&#64;|arroba', '@', full_text, flags=re.IGNORECASE)
        deob = re.sub(r'\s*\[dot\]\s*|\s*\(dot\)\s*|\{dot\}|&#46;|punto', '.', deob, flags=re.IGNORECASE)
        emails = EMAIL_REGEX.findall(deob)
        valid = [e for e in emails if _is_valid_email(e)]
        if valid:
            result["email"] = valid[0]

    # 7. Phone: scan tel: hrefs then full-text PHONE_TEXT_REGEX
    if not result["telefono"]:
        tel_matches = TEL_HREF_REGEX.findall(str(soup))
        if tel_matches:
            result["telefono"] = tel_matches[0].strip()

    if not result["telefono"]:
        phone_m = PHONE_TEXT_REGEX.search(soup.get_text(" "))
        if phone_m and len(re.sub(r'\D', '', phone_m.group())) >= 8:
            result["telefono"] = phone_m.group().strip()


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
    # Try contact pages first (more likely to have email), then homepage fallback
    pages_to_try = [
        base_url + "/contacto",
        base_url,                          # homepage second — most AR sites have Contáctenos in footer
        base_url + "/contactanos",
        base_url + "/contact",
        base_url + "/contact-us",
        base_url + "/sobre-nosotros",
        base_url + "/nosotros",
        base_url + "/acerca-de",
        base_url + "/acerca",
        base_url + "/empresa",
        base_url + "/quienes-somos",
        base_url + "/pages/contact",       # Shopify
        base_url + "/pages/contactanos",   # Shopify
        base_url + "/pages/nosotros",
        base_url + "/pages/acerca-de",
        base_url + "/paginas/contacto",    # Tiendanube
        base_url + "/info",
    ]

    HEAD_BYTES = 80_000    # first 80KB covers <head> JSON-LD, meta, and nav
    TAIL_BYTES = 150_000   # last 150KB covers footer where emails live
    SMALL_PAGE = HEAD_BYTES + TAIL_BYTES   # pages under this → read fully

    try:
        with httpx.Client(timeout=12, follow_redirects=True) as client:
            for page_url in pages_to_try:
                try:
                    # Stream response — read up to TAIL_BYTES past SMALL_PAGE limit
                    raw_chunks: list[bytes] = []
                    total = 0
                    with client.stream("GET", page_url, headers=_ENRICH_HEADERS) as resp:
                        if resp.status_code != 200:
                            continue
                        for chunk in resp.iter_bytes(chunk_size=8192):
                            raw_chunks.append(chunk)
                            total += len(chunk)
                            if total >= SMALL_PAGE + TAIL_BYTES:
                                break  # hard cap ~380KB per page

                    raw_content = b"".join(raw_chunks)

                    # For large pages keep head + tail so we always catch the footer
                    if len(raw_content) > SMALL_PAGE:
                        raw = raw_content[:HEAD_BYTES] + raw_content[-TAIL_BYTES:]
                    else:
                        raw = raw_content
                    del raw_content, raw_chunks

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


def _discover_website(empresa: str, ciudad: str, provincia: str = "") -> str:
    """Free website discovery via DuckDuckGo HTML search (no API key)."""
    if not empresa:
        return ""
    return discover_website_ddg(empresa, ciudad, provincia)


# ─────────────────────────────────────────────
# BACKGROUND TASKS
# ─────────────────────────────────────────────

def _run_scraper_job(
    job_id: str,
    sources: List[str],
    queries: List[str],
    api_key: str,
    max_per_query: int,
    tipo_cliente: str = "lead",
    source_options: Optional[dict] = None,
    org_id: str = None,
):
    scoped_db = ScopedSupabaseClient(db, org_id)
    source_options = source_options or {}
    total_found = 0
    new_found = 0
    num_sources = len(sources)

    try:
        scoped_db.update("scraper_jobs", job_id, {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "total": num_sources,
            "progress": 0,
        })

        for source_index, source_id in enumerate(sources):
            iter_fn = SOURCE_REGISTRY.get(source_id)
            if not iter_fn:
                logger.warning("Unknown scraper source %r, skipping", source_id)
                continue

            kwargs = {"tipo_cliente": tipo_cliente, **source_options.get(source_id, {})}
            if source_id == "google_places":
                kwargs["api_key"] = api_key
                kwargs.setdefault("queries", queries)
                kwargs.setdefault("max_per_query", max_per_query)

            base_progress = int(100 * source_index / num_sources)
            next_progress = int(100 * (source_index + 1) / num_sources)
            records_in_source = 0

            try:
                for record in iter_fn(**kwargs):
                    total_found += 1
                    records_in_source += 1
                    record["score_ia"] = _score_lead(record)

                    try:
                        existing = scoped_db.select(
                            "leads",
                            filters={
                                "empresa": f"eq.{record['empresa']}",
                                "tipo_cliente": f"eq.{tipo_cliente}",
                            },
                            limit=1,
                        )
                        if not existing:
                            scoped_db.insert("leads", record)
                            new_found += 1
                    except Exception:
                        new_found += 1

                    if total_found % 10 == 0:
                        progress = base_progress
                        if next_progress > base_progress:
                            progress = min(next_progress - 1, base_progress + records_in_source // 3)
                        scoped_db.update("scraper_jobs", job_id, {
                            "progress": progress,
                            "new_found": new_found,
                            "total_found": total_found,
                        })
            except NotImplementedError as exc:
                logger.warning("Skipping source %r: %s", source_id, exc)
                continue
            except PlacesAPIError:
                raise
            except Exception:
                logger.exception("Source %r failed, continuing with remaining sources", source_id)
                continue

            progress = int(100 * (source_index + 1) / num_sources)
            scoped_db.update("scraper_jobs", job_id, {
                "progress": progress,
                "new_found": new_found,
                "total_found": total_found,
            })

        scoped_db.update("scraper_jobs", job_id, {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress": 100,
            "new_found": new_found,
            "total_found": total_found,
        })

    except Exception as exc:
        scoped_db.update("scraper_jobs", job_id, {
            "status": "failed",
            "error_msg": str(exc),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })


def _run_enrichment_job(job_id: str, lead_ids: Optional[List[str]], org_id: str = None):
    scoped_db = ScopedSupabaseClient(db, org_id)
    try:
        scoped_db.update("scraper_jobs", job_id, {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

        if lead_ids:
            ids_str = ",".join(lead_ids)
            all_leads = scoped_db.raw_select("leads", {"select": "*", "id": f"in.({ids_str})", "limit": len(lead_ids)})
        else:
            all_leads = scoped_db.raw_select("leads", {
                "select": "id,empresa,website,email,telefono,instagram,whatsapp,ciudad,provincia",
                "website": "neq.",
                "or": "(email.is.null,email.eq.)",
                "order": "id.asc",
                "limit": 5000,
            })

        total = len(all_leads)
        enriched_count = 0

        scoped_db.update("scraper_jobs", job_id, {"total": total})

        for i, lead in enumerate(all_leads):
            website = lead.get("website", "") or ""

            # If no website on file, try to discover it for free via DuckDuckGo
            if not website and lead.get("empresa"):
                website = _discover_website(
                    lead.get("empresa", ""),
                    lead.get("ciudad", ""),
                    lead.get("provincia", ""),
                )
                if website:
                    scoped_db.update("leads", lead["id"], {"website": website})

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
                scoped_db.update("leads", lead["id"], update_data)
                enriched_count += 1

            del enrich, update_data

            # Run GC every 25 leads to reclaim BS4 / httpx memory
            if (i + 1) % 25 == 0:
                gc.collect()

            time.sleep(0.5)
            progress = int(((i + 1) / max(total, 1)) * 100)
            scoped_db.update("scraper_jobs", job_id, {
                "progress": progress,
                "new_found": enriched_count,
            })

        del all_leads
        gc.collect()

        scoped_db.update("scraper_jobs", job_id, {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress": 100,
            "new_found": enriched_count,
            "total_found": total,
        })

    except Exception as exc:
        scoped_db.update("scraper_jobs", job_id, {
            "status": "failed",
            "error_msg": str(exc),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@router.post("/start")
def start_scraper(body: ScraperStartRequest, background_tasks: BackgroundTasks, current_org: OrgContext = Depends(get_current_org)):
    sources = body.sources or DEFAULT_SOURCES

    api_key = body.google_api_key or settings.GOOGLE_API_KEY
    if "google_places" in sources and not api_key:
        raise HTTPException(
            status_code=400,
            detail="Google API key required for the google_places source. Pass google_api_key in the request body or set GOOGLE_API_KEY env var.",
        )

    # Auto-fail any stuck jobs before checking for conflicts
    stuck = current_org.db.raw_select("scraper_jobs", {"select": "id,status,started_at,created_at", "status": "in.(pending,running)", "limit": 10})
    _auto_fail_stuck_jobs(stuck, current_org.db)

    # Prevent duplicate concurrent jobs
    active = current_org.db.raw_select("scraper_jobs", {"select": "id,status", "status": "in.(pending,running)", "limit": 1})
    if active:
        raise HTTPException(status_code=409, detail="Ya hay un job corriendo. Esperá a que termine antes de iniciar otro.")

    tipo_cliente = body.tipo_cliente or "lead"
    queries: List[str] = []
    if "google_places" in sources:
        if body.queries:
            queries = body.queries
        elif tipo_cliente == "mayorista":
            queries = MAYORISTA_QUERIES
        else:
            queries = DEFAULT_QUERIES

    job = current_org.db.insert("scraper_jobs", {
        "status": "pending",
        "queries": queries,
        "sources": sources,
        "progress": 0,
        "total": len(sources),
        "new_found": 0,
        "total_found": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    job_id = job.get("id")
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to create scraper job")

    org_id = current_org.organization_id
    background_tasks.add_task(
        _run_scraper_job, str(job_id), sources, queries, api_key, body.max_per_query,
        tipo_cliente, body.source_options, org_id,
    )

    return {"job_id": job_id, "status": "pending", "sources": sources, "tipo_cliente": tipo_cliente}


@router.get("/jobs")
def list_jobs(current_org: OrgContext = Depends(get_current_org)):
    jobs = current_org.db.select("scraper_jobs", order="created_at.desc", limit=20)
    jobs = _auto_fail_stuck_jobs(jobs, current_org.db)
    return {"data": jobs}


@router.get("/stream/{job_id}")
async def stream_job_progress(job_id: str, current_org: OrgContext = Depends(get_current_org)):
    jobs = current_org.db.select("scraper_jobs", filters={"id": f"eq.{job_id}"}, limit=1)
    if not jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    org_id = current_org.organization_id

    async def event_generator():
        scoped_db = ScopedSupabaseClient(db, org_id)
        while True:
            jobs = scoped_db.select("scraper_jobs", filters={"id": f"eq.{job_id}"}, limit=1)
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
def run_scraper(body: ScraperStartRequest, background_tasks: BackgroundTasks, current_org: OrgContext = Depends(get_current_org)):
    """Alias for /start — used by the frontend."""
    return start_scraper(body, background_tasks, current_org)


STUCK_JOB_TIMEOUT_MINUTES = 180


def _auto_fail_stuck_jobs(jobs: list, scoped_db) -> list:
    """Mark running/pending jobs older than STUCK_JOB_TIMEOUT_MINUTES as failed."""
    now = datetime.now(timezone.utc)
    for job in jobs:
        if job.get("status") not in ("running", "pending"):
            continue
        started_raw = job.get("started_at") or job.get("created_at")
        if not started_raw:
            continue
        try:
            started = datetime.fromisoformat(started_raw.replace("Z", "+00:00"))
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            elapsed = (now - started).total_seconds() / 60
            if elapsed > STUCK_JOB_TIMEOUT_MINUTES:
                scoped_db.update("scraper_jobs", job["id"], {
                    "status": "failed",
                    "error_msg": f"Cancelado automáticamente (sin actividad por {int(elapsed)} min)",
                    "completed_at": now.isoformat(),
                })
                job["status"] = "failed"
                job["error_msg"] = f"Cancelado automáticamente (sin actividad por {int(elapsed)} min)"
        except Exception:
            pass
    return jobs


@router.get("/history")
def get_history(current_org: OrgContext = Depends(get_current_org)):
    """Frontend-compatible alias for /jobs with mapped field names."""
    jobs = current_org.db.select("scraper_jobs", order="created_at.desc", limit=20)
    jobs = _auto_fail_stuck_jobs(jobs, current_org.db)
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
            "sources": job.get("sources"),
        }
        for job in jobs
    ]
    return {"items": items}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, current_org: OrgContext = Depends(get_current_org)):
    """Force-cancel a running or pending job."""
    jobs = current_org.db.select("scraper_jobs", filters={"id": f"eq.{job_id}"}, limit=1)
    if not jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    job = jobs[0]
    if job.get("status") not in ("running", "pending"):
        raise HTTPException(status_code=400, detail="El job ya terminó")
    current_org.db.update("scraper_jobs", job_id, {
        "status": "failed",
        "error_msg": "Cancelado manualmente",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True}


@router.get("/progress")
async def stream_latest_progress(current_org: OrgContext = Depends(get_current_org)):
    """SSE stream for the most recent job — used by the frontend."""
    org_id = current_org.organization_id

    async def event_generator():
        scoped_db = ScopedSupabaseClient(db, org_id)
        while True:
            jobs = scoped_db.select("scraper_jobs", order="created_at.desc", limit=1)
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
def start_enrichment(body: EnrichRequest, background_tasks: BackgroundTasks, current_org: OrgContext = Depends(get_current_org)):
    # Auto-fail stuck jobs before conflict check
    stuck = current_org.db.raw_select("scraper_jobs", {"select": "id,status,started_at,created_at", "status": "in.(pending,running)", "limit": 10})
    _auto_fail_stuck_jobs(stuck, current_org.db)

    # Prevent duplicate concurrent jobs
    active = current_org.db.raw_select("scraper_jobs", {"select": "id,status", "status": "in.(pending,running)", "limit": 1})
    if active:
        raise HTTPException(status_code=409, detail="Ya hay un job corriendo. Esperá a que termine antes de iniciar otro.")

    job = current_org.db.insert("scraper_jobs", {
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

    org_id = current_org.organization_id
    background_tasks.add_task(_run_enrichment_job, str(job_id), body.lead_ids, org_id)

    return {"job_id": job_id, "status": "pending"}

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
    # ── Sahumerios e inciensos ──────────────────
    "tienda sahumerios Buenos Aires",
    "tienda sahumerios Córdoba",
    "tienda sahumerios Rosario",
    "tienda sahumerios Mendoza",
    "tienda sahumerios Mar del Plata",
    "tienda sahumerios Tucumán",
    "tienda sahumerios Salta",
    "tienda sahumerios La Plata",
    "tienda sahumerios Santa Fe",
    "tienda sahumerios Neuquén",
    "tienda sahumerios Bahía Blanca",
    "tienda sahumerios Corrientes",
    "tienda sahumerios Resistencia",
    "tienda sahumerios Paraná",
    "tienda sahumerios Misiones Posadas",
    # ── Holística / esotérica / mística ─────────
    "tienda holistica Buenos Aires",
    "tienda holistica Córdoba",
    "tienda holistica Rosario",
    "tienda esoterica Mendoza",
    "tienda mistica Argentina",
    "tienda new age Argentina",
    "tienda espiritual Argentina",
    "santeria argentina",
    "articulos religiosos esotericos Argentina",
    "tienda chakras cristales Argentina",
    # ── Decoración oriental / feng shui ─────────
    "tienda feng shui Argentina",
    "tienda articulos orientales Argentina",
    "bazar oriental Buenos Aires",
    "tienda budista articulos Argentina",
    "tienda zen decoracion Argentina",
    "fuente agua feng shui tienda Argentina",
    "lampara sal himalaya tienda Argentina",
    "tienda decoracion espiritual Argentina",
    # ── Regalos y objetos de arte ─────────────
    "tienda regalos originales Buenos Aires",
    "tienda regalos esotericos Argentina",
    "bazar artesanal Argentina",
    "tienda artesanias decoracion Argentina",
    "tienda objetos de resina artesanal Argentina",
    "tienda cuarzos minerales Argentina",
    # ── Velas y aromas ──────────────────────────
    "tienda velas aromas Argentina",
    "tienda aromaterapia difusores Argentina",
    "tienda velas decorativas Argentina",
    # ── Ciudades del interior (menos exploradas) ─
    "tienda holistica San Juan",
    "tienda esoterica San Luis",
    "tienda holistica Jujuy",
    "tienda holistica Santiago del Estero",
    "tienda holistica Chaco Resistencia",
    "sahumerios Rio Cuarto Córdoba",
    "tienda esoterica General Roca Neuquén",
    "tienda holistica Tandil",
    "tienda holistica Bahía Blanca",
    "tienda holistica San Rafael Mendoza",
    "tienda esoterica Formosa",
    "tienda holistica Catamarca",
    "tienda holistica La Rioja",
    "tienda holistica Santa Rosa La Pampa",
]

MAYORISTA_QUERIES = [
    # ── Distribuidores y mayoristas directos ────
    "distribuidor sahumerios palo santo Argentina",
    "mayorista articulos esotericos Argentina",
    "distribuidor inciensos aromas mayorista Argentina",
    "importador articulos orientales budistas Argentina",
    "mayorista lamparas sal himalaya Argentina",
    "distribuidor fuentes agua decorativas Argentina",
    "mayorista velas decorativas aromas Argentina",
    "importador estatuas resina buda elefante Argentina",
    "mayorista cascadas de humo incienso Argentina",
    "distribuidor articulos feng shui Argentina",
    "mayorista hornillos sahumadores ceramica Argentina",
    # ── Cadenas y multi-locales ──────────────────
    "cadena tiendas holísticas Argentina",
    "franquicia tienda esotérica Argentina",
    "cadena sahumerios tiendas Argentina",
    # ── Spas y wellness (compran aromas, difusores, lámparas)
    "spa centro bienestar Buenos Aires",
    "spa masajes Córdoba productos aromas",
    "spa wellness Rosario difusores aromas",
    "centro spa Mendoza productos naturales",
    "hotel spa boutique Argentina aromas",
    "spa masajes Mar del Plata",
    # ── Yoga, meditación y terapias ──────────────
    "centro yoga meditación Buenos Aires tienda",
    "centro yoga Córdoba accesorios",
    "estudio yoga Rosario tienda productos",
    "centro meditación mindfulness Argentina tienda",
    "terapeuta holístico con tienda Buenos Aires",
    "centro reiki cristales Buenos Aires",
    "centro terapias alternativas Argentina",
    # ── Dietéticas, herboristerías y naturistas ──
    "herboristería naturista Buenos Aires",
    "dietética productos naturales Argentina",
    "farmacia homeopática naturista Argentina",
    "tienda orgánica naturista Córdoba",
    # ── Decoración y regalo al por mayor ─────────
    "mayorista tiendas regalos decoracion Argentina",
    "distribuidor decoracion oriental hogar Argentina",
    "mayorista objetos decorativos artesanales Argentina",
    "proveedor tiendas regalos Buenos Aires",
    # ── Peluquerías y estéticas (aromas, difusores)
    "peluquería orgánica natural Buenos Aires",
    "salon estética natural productos aromas Argentina",
    "instituto belleza aromaterapia Buenos Aires",
    # ── Mercados y ferias ────────────────────────
    "feria artesanal alternativa Buenos Aires",
    "mercado holístico alternativo Argentina",
    "feria new age esotérica Argentina",
]


ML_PRODUCT_QUERIES = [
    "sahumerios incienso",
    "lampara sal himalaya",
    "palo santo",
    "fuente agua feng shui decorativa",
    "estatua buda resina",
    "difusor aceites esenciales",
    "velas decorativas aromaticas",
    "cuarzos cristales minerales",
    "cascada humo incienso",
    "hornillo sahumador ceramica",
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
WA_REGEX = re.compile(
    r'(?:wa\.me|whatsapp\.com/send|api\.whatsapp\.com/send)[/?&]*(?:phone=)?(\+?\d[\d\s\-]{5,17}\d)',
    re.IGNORECASE,
)
TEL_HREF_REGEX = re.compile(r'href=["\']tel:([+\d\s\-().]{6,20})["\']', re.IGNORECASE)

# Strict Argentine phone: requires +54/54 prefix OR 0XX area code OR (XX) area code
AR_PHONE_REGEX = re.compile(
    r'(?<!\d)'
    r'(?:'
    r'\+?54[\s\-.]?9?[\s\-.]?\d{2,4}[\s\-.]?\d{3,4}[\s\-.]?\d{4}'  # +54 / 54 international
    r'|\(?0\d{2,4}\)?[\s\-./](?:15[\s\-.]?)?\d{3,4}[\s\-.]?\d{4}'  # 0XX area code
    r')'
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


def _decode_cf_email(encoded: str) -> str:
    """Decode CloudFlare's data-cfemail obfuscation."""
    try:
        r = int(encoded[:2], 16)
        return "".join(chr(int(encoded[i:i + 2], 16) ^ r) for i in range(2, len(encoded), 2))
    except Exception:
        return ""


def _extract_from_soup(soup, result: dict) -> None:
    """Extract contact info using BeautifulSoup from parsed HTML."""

    # 1. JSON-LD schema.org — most reliable source (handles nested contactPoint too)
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
            entries = []
            if isinstance(data, list):
                entries = data
            elif isinstance(data, dict):
                entries = data.get("@graph", [data])
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if not result["email"] and entry.get("email"):
                    c = str(entry["email"]).strip()
                    if _is_valid_email(c):
                        result["email"] = c
                if not result["telefono"] and entry.get("telephone"):
                    result["telefono"] = str(entry["telephone"]).strip()
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

    # 2. CloudFlare email protection (data-cfemail) — extremely common on small business sites
    for el in soup.find_all(attrs={"data-cfemail": True}):
        if not result["email"]:
            decoded = _decode_cf_email(el["data-cfemail"])
            if decoded and _is_valid_email(decoded):
                result["email"] = decoded

    # 3. <meta> tags + data-email attributes
    for meta in soup.find_all("meta"):
        content = meta.get("content", "")
        name = (meta.get("name") or meta.get("property") or "").lower()
        if not result["email"] and ("email" in name or "mail" in name):
            if content and _is_valid_email(content):
                result["email"] = content
    for el in soup.find_all(attrs={"data-email": True}):
        if not result["email"]:
            c = el["data-email"].strip()
            if _is_valid_email(c):
                result["email"] = c

    # 4. Microdata: itemprop attributes
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

    # 5. All <a> tags — mailto, tel, instagram, whatsapp
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
            if ig and ig.group(1) not in ("p", "reel", "stories", "explore", "accounts", "sharer"):
                result["instagram"] = f"@{ig.group(1)}"
        if ("wa.me" in href or "whatsapp.com" in href) and not result["whatsapp"]:
            wa = WA_REGEX.search(href)
            if wa:
                num = re.sub(r'[\s\-.]', '', wa.group(1))
                result["whatsapp"] = num

    # 6. Priority zones: footer / contact sections — email and phone
    priority_zones = (
        soup.find_all("footer")
        + soup.find_all(class_=re.compile(r"footer|contact|contacto|pie|bottom|sidebar", re.I))
        + soup.find_all(id=re.compile(r"footer|contact|contacto|pie|bottom|sidebar", re.I))
    )
    for zone in priority_zones:
        zone_text = zone.get_text(" ")
        if not result["email"]:
            emails = EMAIL_REGEX.findall(zone_text)
            valid = [e for e in emails if _is_valid_email(e)]
            if valid:
                result["email"] = valid[0]
        if not result["telefono"]:
            phone_matches = AR_PHONE_REGEX.findall(zone_text)
            if phone_matches:
                result["telefono"] = phone_matches[0].strip()

    # 7. Full page text — email with [at] / (at) deobfuscation variants
    if not result["email"]:
        full_text = soup.get_text(separator=" ")
        deob = re.sub(r'\s*[\[(]at[\])]?\s*|\s+AT\s+', '@', full_text, flags=re.IGNORECASE)
        deob = re.sub(r'\s*[\[(]dot[\])]?\s*', '.', deob, flags=re.IGNORECASE)
        emails = EMAIL_REGEX.findall(deob)
        valid = [e for e in emails if _is_valid_email(e)]
        if valid:
            result["email"] = valid[0]

    # 8. Phone: tel: href scan, then full AR phone pattern over page text
    if not result["telefono"]:
        tel_matches = TEL_HREF_REGEX.findall(str(soup))
        if tel_matches:
            result["telefono"] = tel_matches[0].strip()
    if not result["telefono"]:
        full_text = soup.get_text(separator=" ")
        phone_matches = AR_PHONE_REGEX.findall(full_text)
        for m in phone_matches:
            cleaned = re.sub(r'[\s\-./()]', '', m)
            if 8 <= len(cleaned.lstrip('+')) <= 13:
                result["telefono"] = m.strip()
                break

    # 9. If we have a WhatsApp number but no phone, derive phone from it
    if result.get("whatsapp") and not result["telefono"]:
        wa_digits = re.sub(r'[^\d]', '', result["whatsapp"])
        # +54 9 11 XXXX-XXXX → format nicely
        if wa_digits.startswith("549") and len(wa_digits) == 13:
            result["telefono"] = f"+{wa_digits}"
        elif wa_digits.startswith("54") and len(wa_digits) >= 10:
            result["telefono"] = f"+{wa_digits}"
        elif len(wa_digits) >= 8:
            result["telefono"] = wa_digits


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
    # Contact/about pages first (concentrated contact info), homepage as final fallback
    pages_to_try = [
        base_url + "/contacto",
        base_url + "/contactanos",
        base_url + "/contact",
        base_url + "/contact-us",
        base_url + "/pages/contact",       # Shopify
        base_url + "/pages/contactanos",   # Shopify
        base_url + "/pages/nosotros",      # Shopify
        base_url + "/pages/about",         # Shopify
        base_url + "/sobre-nosotros",
        base_url + "/nosotros",
        base_url + "/quienes-somos",
        base_url + "/acerca-de",
        base_url + "/info",
        base_url,                          # homepage last — largest, try only if needed
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

        if lead_ids:
            ids_str = ",".join(lead_ids)
            all_leads = db.raw_select(
                "leads",
                {"select": "id,empresa,website,email,telefono,instagram,whatsapp,rating,reviews_count,score_ia",
                 "id": f"in.({ids_str})", "limit": len(lead_ids)},
            )
        else:
            # Fetch ALL leads that have a website but are missing email OR phone.
            # select_all paginates in batches of 1000 so memory stays low.
            candidates = db.select_all(
                "leads",
                filters={"website": "not.is.null"},
                select_cols="id,empresa,website,email,telefono,instagram,whatsapp,rating,reviews_count,score_ia",
            )
            all_leads = [
                l for l in candidates
                if not l.get("email") or not l.get("telefono")
            ]
            del candidates
            gc.collect()

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

            if (i + 1) % 25 == 0:
                gc.collect()

            time.sleep(0.2)
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


def _run_ml_scraper_job(job_id: str):
    """Scrape MercadoLibre public API for sellers of holistic/esoteric products."""
    import httpx

    db.update("scraper_jobs", job_id, {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "total": len(ML_PRODUCT_QUERIES) * 2,
        "progress": 0,
    })

    seen_sellers: set = set()
    new_leads = 0
    step = 0

    try:
        with httpx.Client(timeout=15) as client:
            for query in ML_PRODUCT_QUERIES:
                for offset in [0, 50]:
                    step += 1
                    try:
                        resp = client.get(
                            "https://api.mercadolibre.com/sites/MLA/search",
                            params={"q": query, "limit": 50, "offset": offset},
                        )
                        if resp.status_code != 200:
                            continue
                        results = resp.json().get("results", [])

                        for item in results:
                            seller = item.get("seller", {})
                            seller_id = seller.get("id")
                            if not seller_id or seller_id in seen_sellers:
                                continue
                            seen_sellers.add(seller_id)

                            # Only established sellers
                            rep = seller.get("seller_reputation", {})
                            transactions = rep.get("transactions", {}).get("total", 0)
                            if transactions < 20:
                                continue

                            nickname = seller.get("nickname") or f"ML-{seller_id}"
                            permalink = f"https://www.mercadolibre.com.ar/perfil/{nickname}"

                            # Skip if already in DB
                            existing = db.select("leads", filters={
                                "empresa": f"eq.{nickname}",
                            }, limit=1)
                            if existing:
                                continue

                            # Fetch seller detail for city/province
                            city, state = "", ""
                            try:
                                time.sleep(0.1)
                                det = client.get(f"https://api.mercadolibre.com/users/{seller_id}")
                                if det.status_code == 200:
                                    d = det.json()
                                    city = (d.get("address") or {}).get("city", "") or ""
                                    state = (d.get("address") or {}).get("state", "") or ""
                            except Exception:
                                pass

                            record = {
                                "empresa": nickname,
                                "rubro": "Vendedor MercadoLibre",
                                "ciudad": city,
                                "provincia": state,
                                "website": permalink,
                                "fuente": "MercadoLibre API",
                                "estado": "nuevo",
                                "tipo_cliente": "mayorista",
                                "fecha_extraccion": datetime.now(timezone.utc).date().isoformat(),
                                "observaciones": f"Ventas ML: {transactions}",
                            }
                            record["score_ia"] = _score_lead(record)
                            try:
                                db.insert("leads", record)
                                new_leads += 1
                            except Exception:
                                pass

                        time.sleep(0.4)
                    except Exception:
                        pass

                    progress = int((step / (len(ML_PRODUCT_QUERIES) * 2)) * 100)
                    db.update("scraper_jobs", job_id, {
                        "progress": progress,
                        "new_found": new_leads,
                        "total_found": len(seen_sellers),
                    })

        db.update("scraper_jobs", job_id, {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress": 100,
            "new_found": new_leads,
            "total_found": len(seen_sellers),
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


STUCK_JOB_TIMEOUT_MINUTES = 30


def _auto_fail_stuck_jobs(jobs: list) -> list:
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
                db.update("scraper_jobs", job["id"], {
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
def get_history():
    """Frontend-compatible alias for /jobs with mapped field names."""
    jobs = db.select("scraper_jobs", order="created_at.desc", limit=20)
    jobs = _auto_fail_stuck_jobs(jobs)
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


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    """Force-cancel a running or pending job."""
    jobs = db.select("scraper_jobs", filters={"id": f"eq.{job_id}"}, limit=1)
    if not jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    job = jobs[0]
    if job.get("status") not in ("running", "pending"):
        raise HTTPException(status_code=400, detail="El job ya terminó")
    db.update("scraper_jobs", job_id, {
        "status": "failed",
        "error_msg": "Cancelado manualmente",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True}


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    """Delete a completed or failed job from history."""
    jobs = db.select("scraper_jobs", filters={"id": f"eq.{job_id}"}, limit=1)
    if not jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    if jobs[0].get("status") in ("running", "pending"):
        raise HTTPException(status_code=400, detail="Cancelá el job antes de eliminarlo.")
    db.delete("scraper_jobs", job_id)
    return {"ok": True}


@router.post("/reset")
def reset_all_jobs():
    """Force-cancel every running or pending job so a new one can be started."""
    active = db.raw_select(
        "scraper_jobs",
        {"select": "id", "status": "in.(pending,running)", "limit": 50},
    )
    cancelled = 0
    now = datetime.now(timezone.utc).isoformat()
    for job in active:
        try:
            db.update("scraper_jobs", job["id"], {
                "status": "failed",
                "error_msg": "Reiniciado manualmente",
                "completed_at": now,
            })
            cancelled += 1
        except Exception:
            pass
    return {"ok": True, "cancelled": cancelled}


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


@router.post("/run-ml")
def run_ml_scraper(background_tasks: BackgroundTasks):
    """Scrape MercadoLibre API for wholesale buyers of holistic products."""
    active = db.raw_select("scraper_jobs", {"select": "id,status", "status": "in.(pending,running)", "limit": 1})
    if active:
        raise HTTPException(status_code=409, detail="Ya hay un job corriendo. Esperá a que termine.")

    job = db.insert("scraper_jobs", {
        "status": "pending",
        "queries": ["mercadolibre"],
        "progress": 0,
        "new_found": 0,
        "total_found": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    job_id = job.get("id")
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to create job")

    background_tasks.add_task(_run_ml_scraper_job, str(job_id))
    return {"job_id": job_id, "status": "pending"}

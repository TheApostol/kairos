import asyncio
import difflib
import gc
import re
import time
import json
import unicodedata
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
    if not result["email"]:
        priority_zones = (
            soup.find_all("footer")
            + soup.find_all(class_=re.compile(r"footer|contact|contacto|pie|bottom|sidebar", re.I))
            + soup.find_all(id=re.compile(r"footer|contact|contacto|pie|bottom|sidebar", re.I))
        )
        for zone in priority_zones:
            emails = EMAIL_REGEX.findall(zone.get_text(" "))
            valid = [e for e in emails if _is_valid_email(e)]
            if valid:
                result["email"] = valid[0]
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


SKIP_SEARCH_DOMAINS = {
    "google.com", "maps.google", "tripadvisor", "yelp.com",
    "mercadolibre", "infobae.com", "clarin.com", "lanacion.com",
    "paginas-amarillas", "guialocal", "cylex", "dnb.com",
    "duckduckgo.com", "bing.com", "wikipedia.org", "wikidata.org",
    "pinterest.com", "linkedin.com", "tiktok.com", "whatsapp.com",
}

# Social media domains — excluded from website search but used in social search
SOCIAL_DOMAINS = {"facebook.com", "instagram.com", "twitter.com", "youtube.com"}


def _normalize_biz_name(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    for stop in ("srl", "sa", "sas", "shop", "tienda", "store", "distribuidora", "argentina"):
        name = re.sub(rf"\b{stop}\b", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def _names_match(lead_name: str, result_title: str, threshold: float = 0.5) -> bool:
    # Strip common platform suffixes from result title
    result_title = re.sub(r"\s*\(@[^)]+\).*$", "", result_title)  # "Name (@handle) • Instagram"
    result_title = re.sub(r"\s*[-|–].*$", "", result_title)        # "Name - About | Facebook"
    na = _normalize_biz_name(lead_name)
    nb = _normalize_biz_name(result_title)
    if not na or not nb:
        return False
    if na in nb or nb in na:
        return True
    # Any significant word from lead name in result (handles partial matches)
    words_a = {w for w in na.split() if len(w) > 3}
    words_b = set(nb.split())
    if words_a and words_a & words_b:
        return True
    return difflib.SequenceMatcher(None, na, nb).ratio() >= threshold


def _ddg_search(query: str) -> list:
    """Run a DuckDuckGo HTML search. Returns list of {url, title, snippet} dicts."""
    import httpx
    from urllib.parse import urlparse, parse_qs, unquote
    results = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "es-AR,es;q=0.9",
        }
        with httpx.Client(timeout=8, follow_redirects=True) as client:
            resp = client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query, "kl": "ar-es"},
                headers=headers,
            )
        if resp.status_code != 200:
            return []
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        for div in soup.find_all("div", class_="result__body"):
            a_tag = div.find("a", class_="result__a")
            snip_tag = div.find("a", class_="result__snippet")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            if "uddg=" in href:
                try:
                    if href.startswith("//"):
                        href = "https:" + href
                    href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
                except Exception:
                    continue
            if not href.startswith("http"):
                continue
            results.append({
                "url": href.split("?")[0].rstrip("/"),
                "title": a_tag.get_text(strip=True),
                "snippet": snip_tag.get_text(" ", strip=True) if snip_tag else "",
            })
    except Exception:
        pass
    return results


def _search_for_website(nombre: str, ciudad: str = "", provincia: str = "") -> str:
    """DuckDuckGo search to find a business's website by name + location."""
    if not nombre:
        return ""
    location = " ".join(filter(None, [ciudad, provincia]))
    query = f'"{nombre}" {location} Argentina sitio web'.strip()
    for r in _ddg_search(query):
        domain = r["url"].split("/")[2].lower().replace("www.", "")
        skip = SKIP_SEARCH_DOMAINS | SOCIAL_DOMAINS
        if domain and not any(s in domain for s in skip):
            if _names_match(nombre, r["title"]):
                return r["url"]
    return ""


def _search_social(nombre: str, platform: str, ciudad: str = "", provincia: str = "") -> dict:
    """
    Search DuckDuckGo for a business's social media profile on a given platform.
    Returns {url, handle, email, telefono} — all fields verified against lead name.
    """
    result = {"url": "", "handle": "", "email": "", "telefono": ""}
    if not nombre:
        return result
    location = " ".join(filter(None, [ciudad, provincia]))
    query = f'site:{platform} "{nombre}" {location} Argentina'.strip()
    for r in _ddg_search(query):
        if platform not in r["url"]:
            continue
        if not _names_match(nombre, r["title"]):
            continue
        result["url"] = r["url"]
        # Instagram handle from URL
        if "instagram.com" in r["url"]:
            ig_m = re.search(r"instagram\.com/([A-Za-z0-9._]{1,30})", r["url"])
            if ig_m and ig_m.group(1) not in ("p", "reel", "stories", "explore", "accounts", "tv"):
                result["handle"] = "@" + ig_m.group(1)
        # Mine snippet for email / phone
        text = r["title"] + " " + r["snippet"]
        emails = [e for e in EMAIL_REGEX.findall(text) if _is_valid_email(e)]
        if emails:
            result["email"] = emails[0]
        ph = PHONE_TEXT_REGEX.search(text)
        if ph and len(re.sub(r"\D", "", ph.group())) >= 8:
            result["telefono"] = ph.group().strip()
        break  # first matching result
    return result


def _scrape_ig_meta(handle: str) -> dict:
    """Scrape public Instagram profile for website link and contact info in bio."""
    import httpx
    result = {"website": "", "email": "", "telefono": ""}
    username = handle.lstrip("@")
    if not username:
        return result
    url = f"https://www.instagram.com/{username}/"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15",
            "Accept-Language": "es-AR",
        }
        with httpx.Client(timeout=8, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
        if resp.status_code != 200:
            return result
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        # Bio sometimes in og:description: "N Followers, N Following - Bio text"
        og = soup.find("meta", property="og:description")
        if og:
            bio = re.sub(r"^\d.*?-\s*", "", og.get("content", ""))
            emails = [e for e in EMAIL_REGEX.findall(bio) if _is_valid_email(e)]
            if emails:
                result["email"] = emails[0]
            ph = PHONE_TEXT_REGEX.search(bio)
            if ph and len(re.sub(r"\D", "", ph.group())) >= 8:
                result["telefono"] = ph.group().strip()
        # External link in bio (often a linktree or direct site)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and "instagram.com" not in href:
                parsed_domain = href.split("/")[2].lower()
                if not any(s in parsed_domain for s in SKIP_SEARCH_DOMAINS | SOCIAL_DOMAINS):
                    result["website"] = href.split("?")[0].rstrip("/")
                    break
    except Exception:
        pass
    return result


def _scrape_fb_about(fb_url: str) -> dict:
    """Scrape mobile Facebook page's about section for contact info."""
    import httpx
    result = {"email": "", "telefono": "", "website": ""}
    mobile_url = fb_url.replace("www.facebook.com", "m.facebook.com").rstrip("/") + "/?v=info"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
            "Accept-Language": "es-AR",
        }
        with httpx.Client(timeout=8, follow_redirects=True) as client:
            resp = client.get(mobile_url, headers=headers)
        if resp.status_code != 200:
            return result
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        _extract_from_soup(soup, result)
        # Also grab any non-FB external links as website
        if not result["website"]:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http") and "facebook.com" not in href:
                    domain = href.split("/")[2].lower()
                    if not any(s in domain for s in SKIP_SEARCH_DOMAINS | SOCIAL_DOMAINS):
                        result["website"] = href.split("?")[0].rstrip("/")
                        break
    except Exception:
        pass
    return result


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
    # Contact pages first (most likely to have email), then homepage as fallback
    pages_to_try = [
        base_url + "/contacto",
        base_url + "/contactanos",
        base_url + "/contact",
        base_url + "/pages/contact",       # Shopify
        base_url + "/pages/contactanos",   # Shopify
        base_url + "/paginas/contacto",    # Tiendanube
        base_url + "/nosotros",
        base_url + "/pages/nosotros",
        base_url,                          # homepage last
    ]

    HEAD_BYTES = 80_000    # first 80KB covers <head> JSON-LD, meta, and nav
    TAIL_BYTES = 150_000   # last 150KB covers footer where emails live
    SMALL_PAGE = HEAD_BYTES + TAIL_BYTES   # pages under this → read fully

    try:
        with httpx.Client(timeout=8, follow_redirects=True) as client:
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
                                inserted = db.insert("leads", record)
                                results.append({**record, "id": inserted.get("id")})
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

        # Auto-enrich only the NEW leads that have websites (fast, targeted)
        new_lead_ids = [str(r["id"]) for r in results if r.get("id") and r.get("website")]
        if new_lead_ids:
            try:
                enrich_job = db.insert("scraper_jobs", {
                    "status": "pending",
                    "queries": ["enrichment"],
                    "progress": 0,
                    "new_found": 0,
                    "total_found": 0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                enrich_job_id = enrich_job.get("id")
                if enrich_job_id:
                    _run_enrichment_job(str(enrich_job_id), new_lead_ids)
            except Exception:
                pass

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

        COLS = "id,empresa,website,email,telefono,instagram,whatsapp,ciudad,provincia"

        if lead_ids:
            ids_str = ",".join(lead_ids)
            all_leads = db.raw_select("leads", {
                "select": COLS,
                "id": f"in.({ids_str})",
                "limit": len(lead_ids),
            })
        else:
            all_leads = db.raw_select("leads", {
                "select": COLS,
                "or": "(email.is.null,email.eq.)",
                "order": "id.asc",
                "limit": 300,
            })

        total = len(all_leads)
        enriched_count = 0

        db.update("scraper_jobs", job_id, {"total": total})

        for i, lead in enumerate(all_leads):
            nombre  = lead.get("empresa", "")
            ciudad  = lead.get("ciudad", "")
            prov    = lead.get("provincia", "")
            website = (lead.get("website") or "").strip()
            update_data: dict = {}

            def _has(field: str) -> bool:
                return bool(lead.get(field) or update_data.get(field))

            # ── Phase 1: Website ──────────────────────────────────────────
            if not website:
                found = _search_for_website(nombre, ciudad, prov)
                if found:
                    website = found
                    update_data["website"] = found
                    lead["website"] = found
                time.sleep(1)

            if website:
                w_info = _scrape_website(website)
                for field in ("email", "instagram", "whatsapp", "telefono"):
                    if w_info.get(field) and not _has(field):
                        update_data[field] = w_info[field]
                del w_info

            # ── Phase 2: Instagram ────────────────────────────────────────
            if not _has("email"):
                ig = _search_social(nombre, "instagram.com", ciudad, prov)
                time.sleep(1)
                if ig.get("handle") and not _has("instagram"):
                    update_data["instagram"] = ig["handle"]
                if ig.get("email") and not _has("email"):
                    update_data["email"] = ig["email"]
                if ig.get("telefono") and not _has("telefono"):
                    update_data["telefono"] = ig["telefono"]

                # Scrape IG profile for bio link → gives us the real website
                if ig.get("handle") and not _has("email"):
                    ig_meta = _scrape_ig_meta(ig["handle"])
                    if ig_meta.get("email") and not _has("email"):
                        update_data["email"] = ig_meta["email"]
                    if ig_meta.get("telefono") and not _has("telefono"):
                        update_data["telefono"] = ig_meta["telefono"]
                    if ig_meta.get("website") and not _has("website"):
                        update_data["website"] = ig_meta["website"]
                        lead["website"] = ig_meta["website"]
                        # Scrape that site too
                        w2 = _scrape_website(ig_meta["website"])
                        for field in ("email", "whatsapp", "telefono"):
                            if w2.get(field) and not _has(field):
                                update_data[field] = w2[field]
                        del w2

            # ── Phase 3: Facebook ─────────────────────────────────────────
            if not _has("email"):
                fb = _search_social(nombre, "facebook.com", ciudad, prov)
                time.sleep(1)
                if fb.get("email") and not _has("email"):
                    update_data["email"] = fb["email"]
                if fb.get("telefono") and not _has("telefono"):
                    update_data["telefono"] = fb["telefono"]
                if fb.get("url"):
                    fb_about = _scrape_fb_about(fb["url"])
                    for field in ("email", "telefono", "website"):
                        if fb_about.get(field) and not _has(field):
                            update_data[field] = fb_about[field]
                    del fb_about

            # ── Save ──────────────────────────────────────────────────────
            if update_data:
                merged = {**lead, **update_data}
                update_data["score_ia"] = _score_lead(merged)
                update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                db.update("leads", lead["id"], update_data)
                enriched_count += 1

            del update_data

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

    # Auto-fail any stuck jobs before checking for conflicts
    stuck = db.raw_select("scraper_jobs", {"select": "id,status,started_at,created_at", "status": "in.(pending,running)", "limit": 10})
    _auto_fail_stuck_jobs(stuck)

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


STUCK_JOB_TIMEOUT_MINUTES = 90


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
    # Auto-fail stuck jobs before conflict check
    stuck = db.raw_select("scraper_jobs", {"select": "id,status,started_at,created_at", "status": "in.(pending,running)", "limit": 10})
    _auto_fail_stuck_jobs(stuck)

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

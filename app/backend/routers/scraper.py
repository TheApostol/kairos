import asyncio
import concurrent.futures
import gc
import logging
import re
import json
import threading
import unicodedata
from datetime import datetime, timezone
from typing import Optional, List
from urllib.parse import urljoin, urlparse
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.auth import OrgContext, get_current_org
from services.supabase_client import db, ScopedSupabaseClient
from services.scraping_utils import discover_website_ddg
from sources import SOURCE_REGISTRY, DEFAULT_SOURCES
from sources.google_places import DEFAULT_QUERIES, MAYORISTA_QUERIES, PlacesAPIError
from sources.paginas_amarillas import search_by_name as pa_search_by_name
from sources.overpass import search_by_name as overpass_search_by_name
from sources.google_places import search_by_name as google_places_search_by_name
from config import settings

router = APIRouter(prefix="/scraper", tags=["scraper"])

logger = logging.getLogger(__name__)


class ScraperStartRequest(BaseModel):
    queries: Optional[List[str]] = None
    max_per_query: int = 60
    tipo_cliente: str = "lead"  # "lead" or "mayorista"
    sources: Optional[List[str]] = None
    source_options: Optional[dict] = None


class EnrichRequest(BaseModel):
    lead_ids: Optional[List[str]] = None  # if None, enrich all without email


_BUSINESS_SUFFIX_REGEX = re.compile(
    r"\b(s\.?a\.?s?\.?|s\.?r\.?l\.?|s\.?h\.?|sociedad an[oó]nima|sociedad de responsabilidad limitada)\b",
    re.IGNORECASE,
)


def _normalize_empresa(name: str) -> str:
    """Folds a business name down to a comparable key: strips accents/case,
    common legal suffixes (S.A., S.R.L., ...), and punctuation/whitespace
    differences — so e.g. "Dietética La Salud S.A." and "DIETETICA LA SALUD"
    are recognized as the same lead across sources/spellings."""
    if not name:
        return ""
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    n = n.lower()
    n = _BUSINESS_SUFFIX_REGEX.sub(" ", n)
    n = re.sub(r"[^a-z0-9]+", " ", n).strip()
    return n


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
# Matches wa.me/<phone> links and any whatsapp.com/send(...)?phone=<phone> variant
# (covers api.whatsapp.com, extra query params like text= before phone=, etc.)
WA_REGEX = re.compile(
    r"wa\.me/\+?(\d{6,15})|whatsapp\.com/send[^\"'>]*?phone=\+?(\d{6,15})", re.IGNORECASE
)
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

# Link text/href patterns that indicate a "Contact"/"About us" page when
# crawling a homepage's nav/footer for real links (see _discover_contact_links)
_CONTACT_LINK_REGEX = re.compile(
    r"contact|contacto|nosotros|about|acerca|qui[eé]nes[\s\-]?somos|empresa\b|info\b",
    re.IGNORECASE,
)

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


def _wa_phone(match: "re.Match") -> str:
    """WA_REGEX has two alternative capture groups (wa.me vs whatsapp.com/send) — pick whichever matched."""
    return match.group(1) or match.group(2) or ""


def _normalize_phone(raw: str, keep_plus: bool = True) -> str:
    """Strips formatting noise (spaces, dashes, dots, parens) from a scraped
    phone number. Only adds a leading "+" when the input already carries a
    "+" or an Argentina country code ("54..."); area codes in Argentina vary
    from 2 to 4 digits, so this deliberately doesn't try to insert/strip a
    "9" mobile marker or guess at area-code boundaries — getting that wrong
    would corrupt a working number, which is worse than leaving it as
    digit-cleaned but unprefixed. `keep_plus=False` matches the existing
    `whatsapp` field convention of storing bare digits (no "+")."""
    if not raw:
        return raw
    cleaned = re.sub(r"[^\d+]", "", raw)
    if not cleaned:
        return raw
    has_plus = cleaned.startswith("+")
    digits = cleaned.lstrip("+")
    if not digits:
        return raw
    if keep_plus and (has_plus or digits.startswith("54")):
        return "+" + digits
    return digits


def _reassemble_split_emails(soup) -> list:
    """Some sites split an email across sibling inline elements to dodge
    scrapers, e.g. <span>info</span><span>@</span><span>empresa.com</span> —
    EMAIL_REGEX never matches because no single text node contains the full
    address. Walk every parent of a bare "@" text node and re-run the regex
    against its concatenated text instead."""
    found = []
    for at_node in soup.find_all(string=re.compile(r"@")):
        parent = at_node.parent
        if parent is None:
            continue
        joined = parent.get_text(separator="")
        for e in EMAIL_REGEX.findall(joined):
            if _is_valid_email(e) and e not in found:
                found.append(e)
    return found


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
                # address: PostalAddress schema (LocalBusiness/Organization)
                addr = entry.get("address")
                if isinstance(addr, list):
                    addr = addr[0] if addr else {}
                if isinstance(addr, dict):
                    if not result.get("direccion") and addr.get("streetAddress"):
                        result["direccion"] = str(addr["streetAddress"]).strip()
                    if not result.get("ciudad") and addr.get("addressLocality"):
                        result["ciudad"] = str(addr["addressLocality"]).strip()
                    if not result.get("provincia") and addr.get("addressRegion"):
                        result["provincia"] = str(addr["addressRegion"]).strip()
                elif isinstance(addr, str) and not result.get("direccion"):
                    result["direccion"] = addr.strip()
                # sameAs: social profile links (Organization/LocalBusiness schema)
                same_as = entry.get("sameAs")
                if same_as:
                    if isinstance(same_as, str):
                        same_as = [same_as]
                    for link in same_as if isinstance(same_as, list) else []:
                        link = str(link)
                        if not result["instagram"] and "instagram.com" in link:
                            ig = INSTAGRAM_REGEX.search(link)
                            if ig and ig.group(1) not in ("p", "reel", "stories", "explore", "accounts"):
                                result["instagram"] = f"@{ig.group(1)}"
                        if not result["whatsapp"] and ("wa.me" in link or "whatsapp.com" in link):
                            wa = WA_REGEX.search(link)
                            if wa:
                                phone = _wa_phone(wa)
                                if phone:
                                    result["whatsapp"] = phone
                                    if not result["telefono"]:
                                        result["telefono"] = "+" + phone
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
                phone = _wa_phone(wa)
                if phone:
                    result["whatsapp"] = phone
                    if not result["telefono"]:
                        result["telefono"] = "+" + phone

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

    # 5b. Phone-prefix label scan: "Tel:", "Cel:", "WhatsApp:" in plain elements.
    # A "WhatsApp:" label also feeds result["whatsapp"], not just telefono.
    if not result["telefono"] or not result["whatsapp"]:
        for el in soup.find_all(['p', 'li', 'span', 'div']):
            txt = el.get_text(" ", strip=True)
            label_m = re.search(r'\b(tel[eé]?[f.]?|cel(ular)?|whatsapp|fax)\s*[:\-]', txt, re.I)
            if not label_m:
                continue
            m = PHONE_TEXT_REGEX.search(txt)
            if not m or len(re.sub(r'\D', '', m.group())) < 8:
                continue
            if not result["telefono"]:
                result["telefono"] = m.group().strip()
            if "whatsapp" in label_m.group(1).lower() and not result["whatsapp"]:
                result["whatsapp"] = re.sub(r'\D', '', m.group())
            if result["telefono"] and result["whatsapp"]:
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

    # 6b. Split-email reassembly — catches addresses broken across sibling
    # <span> tags (a pattern some sites use specifically to dodge scrapers).
    if not result["email"]:
        reassembled = _reassemble_split_emails(soup)
        if reassembled:
            result["email"] = reassembled[0]

    # 7. Phone: scan tel: hrefs then full-text PHONE_TEXT_REGEX
    full_html = str(soup)
    if not result["telefono"]:
        tel_matches = TEL_HREF_REGEX.findall(full_html)
        if tel_matches:
            result["telefono"] = tel_matches[0].strip()

    if not result["telefono"]:
        phone_m = PHONE_TEXT_REGEX.search(soup.get_text(" "))
        if phone_m and len(re.sub(r'\D', '', phone_m.group())) >= 8:
            result["telefono"] = phone_m.group().strip()

    # 7b. WhatsApp fallback: scan raw HTML (covers click-to-chat widgets wired
    # via onclick/data- attributes rather than a real <a href>) for wa.me /
    # whatsapp.com links missed by the <a href> pass above.
    if not result["whatsapp"]:
        wa = WA_REGEX.search(full_html)
        if wa:
            phone = _wa_phone(wa)
            if phone:
                result["whatsapp"] = phone
                if not result["telefono"]:
                    result["telefono"] = "+" + phone


def _discover_contact_links(homepage_url: str, soup, max_links: int = 5) -> list[str]:
    """Real crawling: look at the homepage's actual <a> links (nav, footer,
    anywhere) for ones that look like a Contact/About page, instead of only
    guessing static URL paths. Restricted to the same domain, deduped, and
    capped at `max_links` so a single site can't blow up the request budget.
    """
    base_netloc = urlparse(homepage_url).netloc
    seen: set[str] = set()
    candidates: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        text = a.get_text(" ", strip=True)
        if not (_CONTACT_LINK_REGEX.search(href) or _CONTACT_LINK_REGEX.search(text)):
            continue

        absolute = urljoin(homepage_url + "/", href).split("#")[0]
        parsed = urlparse(absolute)
        if parsed.netloc and parsed.netloc != base_netloc:
            continue  # stay on-site — ignore links to other domains
        if absolute in seen:
            continue
        seen.add(absolute)
        candidates.append(absolute)
        if len(candidates) >= max_links:
            break
    return candidates


def _scrape_website(url: str) -> dict:
    import httpx
    try:
        from bs4 import BeautifulSoup
        bs4_available = True
    except ImportError:
        bs4_available = False

    result = {
        "email": "", "instagram": "", "whatsapp": "", "telefono": "",
        "direccion": "", "ciudad": "", "provincia": "",
    }
    if not url or not url.startswith("http"):
        return result

    base_url = url.rstrip("/")
    # Static path guesses, used as a fallback alongside (not instead of) real
    # crawling below, in case the homepage doesn't link its contact page.
    static_guesses = [
        base_url + "/contacto",
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
    # Homepage goes first — we need to read it anyway to discover real
    # contact/about links from its nav/footer before falling back to guesses.
    pages_to_try = [base_url] + static_guesses

    HEAD_BYTES = 80_000    # first 80KB covers <head> JSON-LD, meta, and nav
    TAIL_BYTES = 150_000   # last 150KB covers footer where emails live
    SMALL_PAGE = HEAD_BYTES + TAIL_BYTES   # pages under this → read fully
    MAX_PAGES = 12         # hard cap on total requests per site

    seen_urls: set[str] = set()
    homepage_crawled = False

    try:
        with httpx.Client(timeout=12, follow_redirects=True) as client:
            i = 0
            pages_visited = 0
            while i < len(pages_to_try) and pages_visited < MAX_PAGES:
                page_url = pages_to_try[i]
                i += 1
                if page_url in seen_urls:
                    continue
                seen_urls.add(page_url)
                pages_visited += 1
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
                        if page_url == base_url and not homepage_crawled:
                            homepage_crawled = True
                            discovered = _discover_contact_links(base_url, soup)
                            # Real links take priority over the remaining static
                            # guesses — insert them right after the homepage.
                            new_links = [l for l in discovered if l not in seen_urls and l not in pages_to_try]
                            pages_to_try[i:i] = new_links
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
                            wa_m = WA_REGEX.search(text)
                            if wa_m:
                                phone = _wa_phone(wa_m)
                                if phone:
                                    result["whatsapp"] = phone
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

    result["telefono"] = _normalize_phone(result["telefono"], keep_plus=True)
    result["whatsapp"] = _normalize_phone(result["whatsapp"], keep_plus=False)
    return result


def _discover_website(empresa: str, ciudad: str, provincia: str = "") -> str:
    """Free website discovery via DuckDuckGo HTML search (no API key)."""
    if not empresa:
        return ""
    return discover_website_ddg(empresa, ciudad, provincia)


# ─────────────────────────────────────────────
# BACKGROUND TASKS
# ─────────────────────────────────────────────

def _job_is_cancelled(scoped_db: ScopedSupabaseClient, job_id: str) -> bool:
    """True once `/jobs/{id}/cancel` has flipped this job's row away from
    "running" — checked periodically inside the scraper/enrichment loops so
    a cancelled job actually stops instead of running to completion in the
    background. Without this, the cancel endpoint only updated the DB row;
    the worker thread (which runs jobs synchronously, one at a time) stayed
    blocked inside the old job until it finished naturally — sometimes well
    over an hour, given the rate-limited cross-reference sources — so every
    job queued after a "cancelled" one just sat stuck in "pendiente"."""
    try:
        rows = scoped_db.raw_select("scraper_jobs", {"select": "status", "id": f"eq.{job_id}", "limit": 1})
        return not rows or rows[0].get("status") != "running"
    except Exception:
        return False


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
    source_stats: dict = {s: {"found": 0, "new": 0, "status": "pending"} for s in sources}

    try:
        scoped_db.update("scraper_jobs", job_id, {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "total": num_sources,
            "progress": 0,
        })

        # Pre-load existing leads for this tipo_cliente once, normalized, so
        # dedup works both against history and across sources within this
        # same job (e.g. green_life and overpass finding the same shop under
        # slightly different name spellings) — and so a record is never
        # silently dropped just because a per-record DB lookup failed.
        existing_leads = scoped_db.select_all(
            "leads",
            filters={"tipo_cliente": f"eq.{tipo_cliente}"},
            select_cols="empresa",
        )
        seen_empresas = {_normalize_empresa(lead.get("empresa", "")) for lead in existing_leads}
        seen_empresas.discard("")
        del existing_leads

        for source_index, source_id in enumerate(sources):
            iter_fn = SOURCE_REGISTRY.get(source_id)
            if not iter_fn:
                logger.warning("Unknown scraper source %r, skipping", source_id)
                source_stats[source_id]["status"] = "unknown_source"
                continue

            kwargs = {"tipo_cliente": tipo_cliente, **source_options.get(source_id, {})}
            if source_id == "google_places":
                kwargs["api_key"] = api_key
                kwargs.setdefault("queries", queries)
                kwargs.setdefault("max_per_query", max_per_query)

            base_progress = int(100 * source_index / num_sources)
            next_progress = int(100 * (source_index + 1) / num_sources)
            records_in_source = 0
            stat = source_stats[source_id]
            stat["status"] = "running"

            cancelled = False
            try:
                for record in iter_fn(**kwargs):
                    total_found += 1
                    records_in_source += 1
                    stat["found"] += 1
                    record["score_ia"] = _score_lead(record)

                    key = _normalize_empresa(record.get("empresa", ""))
                    if key and key in seen_empresas:
                        continue  # duplicate — already in DB or already inserted earlier in this job

                    try:
                        scoped_db.insert("leads", record)
                        new_found += 1
                        stat["new"] += 1
                        if key:
                            seen_empresas.add(key)
                    except Exception:
                        logger.warning(
                            "Failed to insert lead %r from source %r",
                            record.get("empresa"), source_id, exc_info=True,
                        )

                    if total_found % 10 == 0:
                        if _job_is_cancelled(scoped_db, job_id):
                            cancelled = True
                            break
                        progress = base_progress
                        if next_progress > base_progress:
                            progress = min(next_progress - 1, base_progress + records_in_source // 3)
                        scoped_db.update("scraper_jobs", job_id, {
                            "progress": progress,
                            "new_found": new_found,
                            "total_found": total_found,
                            "details": {"sources": source_stats},
                        })
            except NotImplementedError as exc:
                logger.warning("Skipping source %r: %s", source_id, exc)
                stat["status"] = "skipped"
                stat["error"] = str(exc)
                continue
            except PlacesAPIError as exc:
                stat["status"] = "failed"
                stat["error"] = str(exc)
                scoped_db.update("scraper_jobs", job_id, {"details": {"sources": source_stats}})
                raise
            except Exception as exc:
                logger.exception("Source %r failed, continuing with remaining sources", source_id)
                stat["status"] = "failed"
                stat["error"] = str(exc)
                continue
            else:
                stat["status"] = "completed"

            if cancelled:
                # Leave the row exactly as /jobs/{id}/cancel left it
                # ("failed" + "Cancelado manualmente") — just stop running.
                return

            progress = int(100 * (source_index + 1) / num_sources)
            scoped_db.update("scraper_jobs", job_id, {
                "progress": progress,
                "new_found": new_found,
                "total_found": total_found,
                "details": {"sources": source_stats},
            })

        scoped_db.update("scraper_jobs", job_id, {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress": 100,
            "new_found": new_found,
            "total_found": total_found,
            "details": {"sources": source_stats},
        })

    except Exception as exc:
        scoped_db.update("scraper_jobs", job_id, {
            "status": "failed",
            "error_msg": str(exc),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "details": {"sources": source_stats},
        })


# Cross-reference sources consulted, in priority order, for whatever fields
# are still missing after the website-discovery/scrape pass below. The free
# directory sources run first since they're free to call; google_places goes
# last and silently no-ops without a network call if GOOGLE_API_KEY isn't
# configured, so it's safe to leave in this list unconditionally.
_CROSS_REFERENCE_SOURCES = [pa_search_by_name, overpass_search_by_name, google_places_search_by_name]
_CROSS_REFERENCE_FIELDS = (
    "website", "email", "instagram", "whatsapp", "telefono", "direccion", "ciudad", "provincia",
)


def _enrich_one_lead(scoped_db: ScopedSupabaseClient, lead: dict) -> dict:
    """Discovers a website (if missing) and scrapes it for contact fields,
    then cross-references whatever's still missing against the other free
    directory sources by business name (see `_CROSS_REFERENCE_SOURCES`).
    Writes any updates straight to `lead`'s row. Returns a stats delta dict
    (same keys as `_run_enrichment_job`'s `field_stats`, plus `enriched`)
    for the caller to aggregate — kept side-effect-free on shared state so
    it's safe to run from a thread pool."""
    stats = {
        "websites_discovered": 0,
        "emails_found": 0,
        "instagram_found": 0,
        "whatsapp_found": 0,
        "telefono_found": 0,
        "direccion_found": 0,
        "no_website": 0,
        "enriched": 0,
    }

    website = lead.get("website", "") or ""
    update_data: dict = {}

    # If no website on file, try to discover it for free via DuckDuckGo.
    if not website and lead.get("empresa"):
        website = _discover_website(
            lead.get("empresa", ""),
            lead.get("ciudad", ""),
            lead.get("provincia", ""),
        )
        if website:
            update_data["website"] = website

    if website:
        enrich = _scrape_website(website)
        for field in ["email", "instagram", "whatsapp", "telefono", "direccion", "ciudad", "provincia"]:
            if enrich.get(field) and not lead.get(field):
                update_data[field] = enrich[field]
    else:
        stats["no_website"] += 1

    # Cross-reference the other free directory sources for whatever's still
    # missing, by business name.
    merged = {**lead, **update_data}
    missing = [f for f in _CROSS_REFERENCE_FIELDS if not merged.get(f)]
    if missing and lead.get("empresa"):
        for search_fn in _CROSS_REFERENCE_SOURCES:
            if not missing:
                break
            try:
                found = search_fn(lead.get("empresa", ""), merged.get("ciudad", ""), merged.get("provincia", ""))
            except Exception:
                logger.warning("Cross-reference lookup failed for lead %r", lead.get("empresa"), exc_info=True)
                continue
            if not found:
                continue
            for field in list(missing):
                value = found.get(field)
                if value:
                    update_data[field] = value
                    merged[field] = value
                    missing.remove(field)

    if update_data:
        if update_data.get("website") and not lead.get("website"):
            stats["websites_discovered"] += 1
        update_data["score_ia"] = _score_lead(merged)
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        scoped_db.update("leads", lead["id"], update_data)
        stats["enriched"] += 1
        for field, stat_key in [
            ("email", "emails_found"),
            ("instagram", "instagram_found"),
            ("whatsapp", "whatsapp_found"),
            ("telefono", "telefono_found"),
        ]:
            if field in update_data:
                stats[stat_key] += 1
        if any(f in update_data for f in ("direccion", "ciudad", "provincia")):
            stats["direccion_found"] += 1

    return stats


def _run_enrichment_job(job_id: str, lead_ids: Optional[List[str]], org_id: str = None):
    scoped_db = ScopedSupabaseClient(db, org_id)
    field_stats = {
        "websites_discovered": 0,
        "emails_found": 0,
        "instagram_found": 0,
        "whatsapp_found": 0,
        "telefono_found": 0,
        "direccion_found": 0,
        "no_website": 0,
    }
    try:
        scoped_db.update("scraper_jobs", job_id, {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

        if lead_ids:
            ids_str = ",".join(lead_ids)
            all_leads = scoped_db.raw_select("leads", {"select": "*", "id": f"in.({ids_str})", "limit": len(lead_ids)})
        else:
            # No "website" filter here: leads with no website on file (the
            # common case for green_life/overpass/datos_gob sources) still
            # need to go through this loop so the by-name DDG discovery
            # below gets a chance to find one.
            all_leads = scoped_db.raw_select("leads", {
                "select": "id,empresa,website,email,telefono,instagram,whatsapp,ciudad,provincia,direccion",
                "or": "(email.is.null,email.eq.)",
                "order": "id.asc",
                "limit": 5000,
            })

        total = len(all_leads)
        enriched_count = 0
        completed = 0
        progress_lock = threading.Lock()

        scoped_db.update("scraper_jobs", job_id, {"total": total, "total_found": total})

        # Not a `with` block: ThreadPoolExecutor.__exit__ calls
        # shutdown(wait=True), which would block this (single) worker thread
        # until every already-submitted lead finishes — including on
        # cancellation, defeating the point. Shut down manually instead so a
        # cancelled job can return immediately (see `cancelled` below).
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        cancelled = False
        try:
            futures = {executor.submit(_enrich_one_lead, scoped_db, lead): lead for lead in all_leads}

            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                lead = futures[future]
                try:
                    delta = future.result()
                except Exception:
                    logger.warning("Failed to enrich lead %r", lead.get("empresa"), exc_info=True)
                    delta = None

                with progress_lock:
                    completed += 1
                    if delta:
                        enriched_count += delta.pop("enriched", 0)
                        for key, value in delta.items():
                            field_stats[key] += value

                    # Run GC periodically to reclaim BS4 / httpx memory
                    if completed % 25 == 0:
                        gc.collect()

                    # Update progress every few completions rather than on
                    # every single one, to avoid a DB write storm from 5
                    # concurrent workers finishing in quick succession.
                    if completed % 5 == 0 or completed == total:
                        if _job_is_cancelled(scoped_db, job_id):
                            cancelled = True
                            break
                        progress = int((completed / max(total, 1)) * 100)
                        scoped_db.update("scraper_jobs", job_id, {
                            "progress": progress,
                            "new_found": enriched_count,
                            "details": field_stats,
                        })
        finally:
            # On cancellation, drop anything not yet started and don't wait
            # for the (up to 5) already-running leads — they finish and exit
            # on their own without blocking the worker from picking up the
            # next pending job.
            executor.shutdown(wait=not cancelled, cancel_futures=cancelled)

        if cancelled:
            # Leave the row exactly as /jobs/{id}/cancel left it ("failed" +
            # "Cancelado manualmente") — just stop running.
            return

        del all_leads
        gc.collect()

        scoped_db.update("scraper_jobs", job_id, {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress": 100,
            "new_found": enriched_count,
            "total_found": total,
            "details": field_stats,
        })

    except Exception as exc:
        scoped_db.update("scraper_jobs", job_id, {
            "status": "failed",
            "error_msg": str(exc),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "details": field_stats,
        })


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@router.post("/start")
def start_scraper(body: ScraperStartRequest, current_org: OrgContext = Depends(get_current_org)):
    sources = body.sources or DEFAULT_SOURCES

    # Jobs are picked up by the separate worker process (see worker.py), which
    # only has access to settings.GOOGLE_API_KEY (an env var) — not to this
    # request's body — so a per-request API key isn't persisted or supported.
    if "google_places" in sources and not settings.GOOGLE_API_KEY:
        if body.sources is not None:
            # Explicitly requested — fail loudly so the caller knows why.
            raise HTTPException(
                status_code=400,
                detail="Google API key required for the google_places source. Set the GOOGLE_API_KEY env var.",
            )
        # Came in only via DEFAULT_SOURCES — drop it silently so default runs
        # keep working before a key is configured; it activates automatically
        # once GOOGLE_API_KEY is set, no other change needed.
        sources = [s for s in sources if s != "google_places"]

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
        "job_type": "scraper",
        "queries": queries,
        "sources": sources,
        "progress": 0,
        "total": len(sources),
        "new_found": 0,
        "total_found": 0,
        "params": {
            "tipo_cliente": tipo_cliente,
            "max_per_query": body.max_per_query,
            "source_options": body.source_options,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    job_id = job.get("id")
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to create scraper job")

    # The worker process (worker.py) polls for pending jobs and runs them —
    # this endpoint only ever enqueues, so a web-process restart/redeploy
    # while the job runs can no longer kill it mid-way.
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
def run_scraper(body: ScraperStartRequest, current_org: OrgContext = Depends(get_current_org)):
    """Alias for /start — used by the frontend."""
    return start_scraper(body, current_org)


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
            "tipo": job.get("job_type") or ("enrichment" if job.get("queries") == ["enrichment"] else "scraper"),
            "sources": job.get("sources"),
            "details": job.get("details"),
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
            if status in ("completed", "failed"):
                payload["details"] = job.get("details")

            yield f"data: {json.dumps(payload)}\n\n"

            if status in ("completed", "failed"):
                return

            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/enrich")
def start_enrichment(body: EnrichRequest, current_org: OrgContext = Depends(get_current_org)):
    # Auto-fail stuck jobs before conflict check
    stuck = current_org.db.raw_select("scraper_jobs", {"select": "id,status,started_at,created_at", "status": "in.(pending,running)", "limit": 10})
    _auto_fail_stuck_jobs(stuck, current_org.db)

    # Prevent duplicate concurrent jobs
    active = current_org.db.raw_select("scraper_jobs", {"select": "id,status", "status": "in.(pending,running)", "limit": 1})
    if active:
        raise HTTPException(status_code=409, detail="Ya hay un job corriendo. Esperá a que termine antes de iniciar otro.")

    job = current_org.db.insert("scraper_jobs", {
        "status": "pending",
        "job_type": "enrichment",
        "queries": ["enrichment"],
        # Enrichment doesn't use the `sources` column at all (it's a
        # scraper-only concept) — set it explicitly to an empty list instead
        # of leaving it to the DB's `["google_places"]` default, which would
        # otherwise show up misleadingly as "Fuentes: google_places" in the
        # job history UI for a job that never touches Google Places.
        "sources": [],
        "progress": 0,
        "new_found": 0,
        "total_found": 0,
        "params": {"lead_ids": body.lead_ids},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    job_id = job.get("id")
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to create enrichment job")

    # Picked up by the worker process (worker.py) — see /start for why.
    return {"job_id": job_id, "status": "pending"}

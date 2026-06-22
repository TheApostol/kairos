"""green-life.com.ar source — ~12K "Tiendas Naturistas" (dietéticas,
herboristerías, suplementos) across Argentina.

Iterates the site's WordPress sitemap (`business-sitemap{1..N}.xml`) for
`/tienda-naturista/{slug}/` detail pages, each of which embeds a confirmed
`LocalBusiness` JSON-LD block with name, address, phone, hours and rating.
"""

import html
import json
import random
import re
from typing import Iterator, Optional

from bs4 import BeautifulSoup

from constants.scraper_targets import RUBRO_KEYWORDS
from services.scraping_utils import RateLimiter, fetch_with_retries, make_lead_record
from . import register_source

BASE_URL = "https://green-life.com.ar"
SITEMAP_INDEX_URL = f"{BASE_URL}/sitemap_index.xml"

_rate_limiter = RateLimiter(min_interval=1.5, jitter=0.5)

_LOC_PATTERN = re.compile(r"<loc>(.*?)</loc>")
_DETAIL_PATTERN = re.compile(r"^https://green-life\.com\.ar/tienda-naturista/[^/]+/$")
_POSTAL_CODE_PREFIX = re.compile(r"^[A-Z]?\d{4}[A-Z]{0,3}\s+")


def _iter_business_sitemaps() -> Iterator[str]:
    """Yields business-sitemap URLs in random order.

    `iter_leads` stops after `max_records` detail pages, and the site has
    ~12K listings across many sitemap files — always visiting them in the
    same (index) order meant every run re-scraped the exact same first
    `max_records` businesses forever, never finding anything new. Shuffling
    which sitemap we start from lets repeated runs sample different parts
    of the catalog over time.
    """
    resp = fetch_with_retries(SITEMAP_INDEX_URL, rate_limiter=_rate_limiter)
    if resp is None or resp.status_code != 200:
        return
    sitemaps = [loc for loc in _LOC_PATTERN.findall(resp.text) if "business-sitemap" in loc]
    random.shuffle(sitemaps)
    yield from sitemaps


def _iter_detail_urls() -> Iterator[str]:
    for sitemap_url in _iter_business_sitemaps():
        resp = fetch_with_retries(sitemap_url, rate_limiter=_rate_limiter)
        if resp is None or resp.status_code != 200:
            continue
        detail_urls = [loc for loc in _LOC_PATTERN.findall(resp.text) if _DETAIL_PATTERN.match(loc)]
        random.shuffle(detail_urls)
        yield from detail_urls


def _parse_street_address(street_address: str) -> tuple[str, str, str]:
    """"Lamadrid 312, C7000 Tandil, Provincia de Buenos Aires, Argentina"
    -> ("Lamadrid 312", "Tandil", "Buenos Aires")"""
    parts = [p.strip() for p in street_address.split(",")]
    direccion = parts[0] if len(parts) > 0 else ""
    ciudad = ""
    provincia = ""
    if len(parts) > 1:
        ciudad = _POSTAL_CODE_PREFIX.sub("", parts[1]).strip()
    if len(parts) > 2:
        provincia = re.sub(r"^Provincia de\s+", "", parts[2], flags=re.IGNORECASE).strip()
    return direccion, ciudad, provincia


def _infer_rubro(description: str) -> str:
    desc_lower = description.lower()
    for kw in RUBRO_KEYWORDS:
        if kw.lower() in desc_lower:
            return "Tienda Naturista / Dietética — " + kw.title()
    return "Tienda Naturista / Dietética"


def _parse_detail_page(url: str, tipo_cliente: str) -> Optional[dict]:
    resp = fetch_with_retries(url, rate_limiter=_rate_limiter)
    if resp is None or resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        if not isinstance(data, dict) or "address" not in data:
            continue

        address = data.get("address", {})
        street_address = html.unescape(address.get("streetAddress", ""))
        direccion, ciudad, provincia = _parse_street_address(street_address)
        if not provincia:
            provincia = re.sub(
                r"^Provincia de\s+", "", html.unescape(address.get("addressLocality", "")), flags=re.IGNORECASE
            ).strip()

        rating = None
        reviews_count = None
        agg = data.get("aggregateRating") or {}
        try:
            best = float(agg.get("bestRating", 10) or 10)
            value = float(agg.get("ratingValue"))
            rating = round(value * 5 / best, 1) if best else None
        except (TypeError, ValueError):
            pass
        try:
            reviews_count = int(agg.get("reviewCount"))
        except (TypeError, ValueError):
            pass

        return make_lead_record(
            empresa=html.unescape(data.get("name", "")),
            rubro=_infer_rubro(data.get("description", "")),
            direccion=direccion,
            ciudad=ciudad,
            provincia=provincia,
            telefono=data.get("telephone", ""),
            rating=rating,
            reviews_count=reviews_count,
            horarios="; ".join(data.get("openingHours", []) or []),
            fuente="green-life.com.ar",
            tipo_cliente=tipo_cliente,
            ficha_url=url,
        )

    return None


@register_source("green_life")
def iter_leads(*, max_records: int = 200, tipo_cliente: str = "lead", **_kwargs) -> Iterator[dict]:
    """Yields lead records parsed from green-life.com.ar business detail pages."""
    count = 0
    for url in _iter_detail_urls():
        if count >= max_records:
            return
        record = _parse_detail_page(url, tipo_cliente)
        if record and record.get("empresa"):
            count += 1
            yield record

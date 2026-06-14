"""paginasamarillas.com.ar source.

Confirmed working listing endpoint: `/b/{category-slug}/{location-slug}?page=N`
returns a server-rendered Next.js page embedding a `__NEXT_DATA__` JSON blob
at `props.pageProps.results` — a list of business dicts with name, contact
links (website/instagram/facebook), address, phones and emails. No
detail-page fetch needed.
"""

import json
import re
from typing import Iterator, Optional

from constants.scraper_targets import build_freetext_queries
from services.scraping_utils import RateLimiter, fetch_with_retries, make_lead_record
from . import register_source

BASE_URL = "https://www.paginasamarillas.com.ar"

_rate_limiter = RateLimiter(min_interval=2.0, jitter=1.0)

_NEXT_DATA_PATTERN = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)

_PAGE_SIZE = 15
_MAX_PAGES_PER_QUERY = 4


def _split_locality(address_locality: str) -> tuple[str, str]:
    """"Buenos Aires|Lomas del Mirador" -> ("Buenos Aires", "Lomas del Mirador")"""
    parts = [p.strip() for p in (address_locality or "").split("|")]
    provincia = parts[0] if len(parts) > 0 else ""
    ciudad = parts[1] if len(parts) > 1 else ""
    return provincia, ciudad


def _first(values) -> str:
    if isinstance(values, list) and values:
        return values[0]
    return ""


def _make_record_from_result(result: dict, rubro_label: str, tipo_cliente: str) -> Optional[dict]:
    name = result.get("name", "").strip()
    if not name:
        return None

    contact = result.get("contactMap") or {}
    main_address = result.get("mainAddress") or {}

    direccion = " ".join(
        filter(None, [main_address.get("streetName", "").strip(), (main_address.get("streetNumber") or "").strip()])
    )
    provincia, ciudad_from_locality = _split_locality(main_address.get("addressLocality", ""))
    ciudad = ciudad_from_locality or main_address.get("localidad", "")

    main_phone = result.get("mainPhone") or {}
    telefono = main_phone.get("phoneToShow", "") or main_phone.get("number", "")

    email = _first(result.get("emails"))
    website = _first(contact.get("WEB"))
    instagram = _first(contact.get("INSTAGRAM"))

    info_url = result.get("infoUrl", "")
    ficha_url = f"{BASE_URL}{info_url}" if info_url.startswith("/") else info_url

    return make_lead_record(
        empresa=name,
        rubro=rubro_label,
        direccion=direccion,
        ciudad=ciudad,
        provincia=provincia,
        telefono=telefono,
        website=website,
        email=email,
        instagram=instagram,
        observaciones=result.get("infoLine", "") or "",
        fuente="Páginas Amarillas",
        tipo_cliente=tipo_cliente,
        ficha_url=ficha_url,
    )


def _iter_listing_results(category_slug: str, location_slug: str) -> Iterator[dict]:
    page = 1
    seen_total: Optional[int] = None
    fetched = 0

    while page <= _MAX_PAGES_PER_QUERY:
        resp = fetch_with_retries(
            f"{BASE_URL}/b/{category_slug}/{location_slug}",
            rate_limiter=_rate_limiter,
            params={"page": page} if page > 1 else None,
            timeout=30,
        )
        if resp is None or resp.status_code != 200:
            return

        m = _NEXT_DATA_PATTERN.search(resp.text)
        if not m:
            return
        try:
            data = json.loads(m.group(1))
        except Exception:
            return

        page_props = data.get("props", {}).get("pageProps", {})
        results = page_props.get("results") or []
        if not results:
            return

        if seen_total is None:
            seen_total = page_props.get("total") or 0

        for result in results:
            yield result
        fetched += len(results)

        if fetched >= seen_total or len(results) < _PAGE_SIZE:
            return
        page += 1


@register_source("paginas_amarillas")
def iter_leads(
    *,
    max_records: int = 300,
    areas: Optional[list[str]] = None,
    rubros: Optional[list[str]] = None,
    tipo_cliente: str = "lead",
    **_kwargs,
) -> Iterator[dict]:
    """Yields lead records from paginasamarillas.com.ar listing pages across
    the configured rubro x location combos."""
    from constants.scraper_targets import GEO_TARGETS, RUBRO_TO_PA_SLUGS

    geo_targets = [g for g in GEO_TARGETS if not areas or g["name"] in areas]
    rubro_slugs = (
        {label: slug for label, slug in RUBRO_TO_PA_SLUGS.items() if label in rubros}
        if rubros
        else RUBRO_TO_PA_SLUGS
    )

    count = 0
    seen_ids: set = set()

    for rubro_label, category_slug, location_slug in build_freetext_queries(geo_targets, rubro_slugs):
        if count >= max_records:
            return

        for result in _iter_listing_results(category_slug, location_slug):
            if count >= max_records:
                return

            result_id = result.get("id")
            if result_id and result_id in seen_ids:
                continue
            if result_id:
                seen_ids.add(result_id)

            record = _make_record_from_result(result, rubro_label, tipo_cliente)
            if record:
                count += 1
                yield record

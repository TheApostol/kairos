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

from constants.scraper_targets import GEO_TARGETS, build_freetext_queries
from services.scraping_utils import (
    GENERIC_BUSINESS_WORDS,
    RateLimiter,
    fetch_with_retries,
    make_lead_record,
    name_tokens,
    slugify,
)
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


def _extract_fields(result: dict) -> Optional[dict]:
    """Pulls the contact/address fields out of one PA search-result dict.
    Shared by `_make_record_from_result` (new-lead creation) and
    `search_by_name` (enrichment cross-reference)."""
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

    return {
        "empresa": name,
        "direccion": direccion,
        "ciudad": ciudad,
        "provincia": provincia,
        "telefono": telefono,
        "website": website,
        "email": email,
        "instagram": instagram,
        "observaciones": result.get("infoLine", "") or "",
        "ficha_url": ficha_url,
    }


def _make_record_from_result(result: dict, rubro_label: str, tipo_cliente: str) -> Optional[dict]:
    fields = _extract_fields(result)
    if not fields:
        return None

    return make_lead_record(
        empresa=fields["empresa"],
        rubro=rubro_label,
        direccion=fields["direccion"],
        ciudad=fields["ciudad"],
        provincia=fields["provincia"],
        telefono=fields["telefono"],
        website=fields["website"],
        email=fields["email"],
        instagram=fields["instagram"],
        observaciones=fields["observaciones"],
        fuente="Páginas Amarillas",
        tipo_cliente=tipo_cliente,
        ficha_url=fields["ficha_url"],
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


def _location_slug_for(ciudad: str, provincia: str) -> str:
    """Maps a lead's free-text ciudad/provincia to a PA location slug.
    Tries an exact (accent/case-insensitive) match against GEO_TARGETS'
    `name` first, then falls back to slugifying provincia directly — PA
    accepts province-level slugs (confirmed: e.g. "santa-fe" returns more
    results than the single-city "rosario" slug), but has no national
    wildcard, so an empty string means "can't search this lead"."""
    ciudad_norm = slugify(ciudad)
    for geo in GEO_TARGETS:
        if slugify(geo["name"]) == ciudad_norm:
            return geo["pa_slug"]
    if provincia:
        return slugify(provincia)
    return ""


def search_by_name(empresa: str, ciudad: str = "", provincia: str = "") -> Optional[dict]:
    """Cross-references a lead against paginasamarillas.com.ar by slugifying
    its name into PA's `/b/{slug}/{location}` route — confirmed via manual
    testing to behave as a free-text business-name search rather than a
    fixed category index (e.g. `/b/farmacia-rucci/rosario` returns exactly
    that business). Returns a flat dict of contact fields for merging into
    an existing lead, or None if no confident match was found.

    Best-effort: requires a resolvable location slug (no national-wide
    search exists on PA), and only accepts a result whose name shares at
    least one non-generic token with `empresa`, to avoid confidently
    merging in an unrelated business's contact info.
    """
    if not empresa:
        return None

    location_slug = _location_slug_for(ciudad, provincia)
    if not location_slug:
        return None

    name_slug = slugify(empresa)
    if not name_slug:
        return None

    empresa_tokens = name_tokens(empresa) - GENERIC_BUSINESS_WORDS

    for result in _iter_listing_results(name_slug, location_slug):
        fields = _extract_fields(result)
        if not fields:
            continue

        if empresa_tokens and not (empresa_tokens & (name_tokens(fields["empresa"]) - GENERIC_BUSINESS_WORDS)):
            continue

        return fields

    return None


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

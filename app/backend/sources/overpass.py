"""OpenStreetMap / Overpass API source.

Free, keyless tag+bbox queries for shops/amenities relevant to the
wellness/natural/esoteric niche in the biggest Argentine commercial cities.
Overpass requires a modest request rate and an identifying User-Agent
(returns HTTP 406 without one — confirmed during development).
"""

import re
from typing import Iterator, Optional

from constants.scraper_targets import GEO_TARGETS, OVERPASS_BBOXES, OVERPASS_TAGS, RUBRO_KEYWORDS
from services.scraping_utils import RateLimiter, fetch_with_retries, make_lead_record
from . import register_source

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Overpass usage policy asks for a modest request rate.
_rate_limiter = RateLimiter(min_interval=6.0, jitter=2.0)

_PROVINCIA_BY_AREA = {geo["name"]: geo["provincia"] for geo in GEO_TARGETS}

_NAME_REGEX = "|".join(re.escape(kw) for kw in RUBRO_KEYWORDS)

_ELEMENT_TYPES = ("node", "way")
_NAME_TAG_KEYS = ("shop", "amenity", "office", "craft", "leisure")


def _build_query(bbox: tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"

    clauses = []
    for el_type in _ELEMENT_TYPES:
        for tag in OVERPASS_TAGS:
            (key, value), = tag.items()
            clauses.append(f'  {el_type}["{key}"="{value}"]({bbox_str});')
        for key in _NAME_TAG_KEYS:
            clauses.append(f'  {el_type}["{key}"]["name"~"{_NAME_REGEX}",i]({bbox_str});')

    return (
        "[out:json][timeout:60];\n(\n"
        + "\n".join(clauses)
        + "\n);\nout center tags;"
    )


def _rubro_from_tags(tags: dict) -> str:
    for key in _NAME_TAG_KEYS:
        if tags.get(key):
            return f"{key}={tags[key]}"
    return "OpenStreetMap"


@register_source("overpass")
def iter_leads(*, areas: Optional[list[str]] = None, tipo_cliente: str = "lead", **_kwargs) -> Iterator[dict]:
    """Yields lead records from Overpass API for each configured bbox."""
    seen: set = set()
    bbox_items = OVERPASS_BBOXES.items()
    if areas:
        bbox_items = [(name, bbox) for name, bbox in bbox_items if name in areas]

    for area_name, bbox in bbox_items:
        query = _build_query(bbox)
        resp = fetch_with_retries(
            OVERPASS_URL,
            method="POST",
            rate_limiter=_rate_limiter,
            data={"data": query},
            timeout=90,
            max_retries=2,
        )
        if resp is None or resp.status_code != 200:
            continue

        try:
            data = resp.json()
        except Exception:
            continue

        for element in data.get("elements", []):
            key = f"{element.get('type')}/{element.get('id')}"
            if key in seen:
                continue
            seen.add(key)

            tags = element.get("tags", {})
            name = tags.get("name", "")
            if not name:
                continue

            direccion = " ".join(
                filter(None, [tags.get("addr:street", ""), tags.get("addr:housenumber", "")])
            )

            yield make_lead_record(
                empresa=name,
                rubro=_rubro_from_tags(tags),
                direccion=direccion,
                ciudad=tags.get("addr:city", ""),
                provincia=tags.get("addr:state", "") or _PROVINCIA_BY_AREA.get(area_name, ""),
                telefono=tags.get("phone", "") or tags.get("contact:phone", ""),
                website=tags.get("website", "") or tags.get("contact:website", ""),
                email=tags.get("email", "") or tags.get("contact:email", ""),
                instagram=tags.get("contact:instagram", ""),
                google_maps_url=f"https://www.openstreetmap.org/{element.get('type')}/{element.get('id')}",
                fuente="OpenStreetMap (Overpass)",
                tipo_cliente=tipo_cliente,
            )

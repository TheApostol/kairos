"""Google Places API source (Text Search + Place Details).

Relocated from `routers/scraper.py` — behavior is unchanged from before the
multi-source refactor. Requires a Google Cloud Places API key with billing
enabled; kept as an optional source now that several free sources exist.
"""

import re
import time
from typing import Iterator, List, Optional

import httpx

from services.scraping_utils import make_lead_record
from . import register_source

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
    # ── Nacional ──
    "tienda sahumerios Argentina",
    "tienda holistica Argentina",
    "tienda esoterica Argentina",
    "tienda new age Argentina",
    "aromaterapia tienda Argentina",
    "velas aromaticas tienda Argentina",
    "lamparas de sal himalaya tienda Argentina",
    "bazar espiritual Argentina",
    "santeria Argentina",
    "cristales y piedras tienda Argentina",
    "tienda naturista aromaterapia Argentina",
    "defumacion hierbas tienda Argentina",
    "decoracion feng shui tienda Argentina",
    "fuente agua decorativa tienda Argentina",

    # ── Buenos Aires (CABA) ──
    "tienda sahumerios Buenos Aires",
    "tienda holistica Buenos Aires",
    "tienda esoterica Buenos Aires",
    "aromaterapia Buenos Aires",
    "cristales piedras Buenos Aires",
    "bazar espiritual Buenos Aires",
    "tienda naturista Buenos Aires",
    "santeria Buenos Aires",
    "libreria esoterica Buenos Aires",
    "velas aromaticas Buenos Aires",
    "lampara sal himalaya Buenos Aires",
    "tienda new age Buenos Aires",

    # ── GBA ──
    "tienda holistica Quilmes",
    "tienda esoterica Morón",
    "sahumerios La Matanza",
    "tienda holistica Lomas de Zamora",
    "sahumerios Avellaneda",
    "tienda holistica San Martín Buenos Aires",
    "tienda esoterica Tigre",
    "sahumerios Lanús",
    "tienda holistica Merlo Buenos Aires",
    "tienda esoterica Florencio Varela",
    "sahumerios Berazategui",
    "tienda holistica Moreno Buenos Aires",
    "tienda esoterica Almirante Brown",
    "sahumerios Tres de Febrero",

    # ── Córdoba ──
    "tienda sahumerios Córdoba",
    "tienda holistica Córdoba",
    "tienda esoterica Córdoba",
    "aromaterapia Córdoba",
    "cristales piedras Córdoba",
    "tienda naturista Córdoba",
    "santeria Córdoba",
    "lampara sal himalaya Córdoba",
    "tienda holistica Río Cuarto",
    "sahumerios Rio Cuarto",
    "tienda holistica Villa María Córdoba",

    # ── Rosario ──
    "tienda sahumerios Rosario",
    "tienda holistica Rosario",
    "tienda esoterica Rosario",
    "aromaterapia Rosario",
    "cristales Rosario",
    "lampara sal himalaya Rosario",

    # ── Mendoza ──
    "tienda sahumerios Mendoza",
    "tienda holistica Mendoza",
    "tienda esoterica Mendoza",
    "aromaterapia Mendoza",
    "cristales piedras Mendoza",

    # ── La Plata ──
    "tienda sahumerios La Plata",
    "tienda holistica La Plata",
    "tienda esoterica La Plata",

    # ── Mar del Plata ──
    "tienda sahumerios Mar del Plata",
    "tienda holistica Mar del Plata",
    "tienda esoterica Mar del Plata",

    # ── Tucumán ──
    "tienda sahumerios Tucumán",
    "tienda holistica Tucumán",
    "tienda esoterica Tucumán",
    "tienda holistica San Miguel de Tucumán",

    # ── Salta ──
    "tienda sahumerios Salta",
    "tienda holistica Salta",
    "tienda esoterica Salta",

    # ── Santa Fe ──
    "tienda sahumerios Santa Fe",
    "tienda holistica Santa Fe",
    "tienda esoterica Santa Fe",

    # ── Neuquén ──
    "tienda sahumerios Neuquén",
    "tienda holistica Neuquén",

    # ── Bahía Blanca ──
    "tienda sahumerios Bahia Blanca",
    "tienda holistica Bahia Blanca",

    # ── Corrientes ──
    "tienda holistica Corrientes",
    "sahumerios Corrientes",

    # ── Chaco ──
    "tienda holistica Resistencia",
    "sahumerios Resistencia",

    # ── Misiones ──
    "tienda holistica Posadas",
    "sahumerios Posadas",

    # ── Jujuy ──
    "tienda sahumerios Jujuy",
    "tienda holistica Jujuy",

    # ── San Juan ──
    "tienda holistica San Juan",
    "sahumerios San Juan",

    # ── Entre Ríos ──
    "tienda holistica Paraná",
    "sahumerios Concordia",
    "tienda holistica Gualeguaychú",

    # ── Patagonia ──
    "tienda holistica Bariloche",
    "sahumerios Bariloche",
    "tienda holistica Comodoro Rivadavia",
    "tienda holistica Río Gallegos",
    "tienda holistica Ushuaia",

    # ── San Luis ──
    "tienda holistica San Luis",

    # ── Catamarca ──
    "tienda holistica Catamarca",

    # ── Santiago del Estero ──
    "tienda holistica Santiago del Estero",

    # ── La Rioja ──
    "tienda holistica La Rioja",

    # ── Formosa ──
    "tienda holistica Formosa",
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


class PlacesAPIError(Exception):
    """Raised when the Google Places API itself reports an error status
    (bad/missing key, quota exceeded, etc). The HTTP request still returns
    200 OK in these cases, so this can't be caught via raise_for_status()."""


def _places_text_search(api_key: str, query: str, page_token: Optional[str] = None) -> dict:
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
        data = resp.json()

    status = data.get("status")
    if status not in ("OK", "ZERO_RESULTS"):
        raise PlacesAPIError(f"{status}: {data.get('error_message', 'Google Places API error')}")
    return data


def _place_details(api_key: str, place_id: str) -> dict:
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


@register_source("google_places")
def iter_leads(
    *,
    api_key: str,
    queries: Optional[List[str]] = None,
    tipo_cliente: str = "lead",
    max_per_query: int = 60,
    **_kwargs,
) -> Iterator[dict]:
    """Yields lead records from Google Places Text Search + Place Details.

    Same pagination/delay behavior as the original inline implementation:
    up to 3 pages per query, 2s delay between pages, 0.1s delay before each
    Place Details call, 0.5s delay between queries.
    """
    if not api_key:
        raise PlacesAPIError("Google API key required for the google_places source")

    queries = queries or DEFAULT_QUERIES
    seen_ids: set = set()

    for query in queries:
        next_page_token = None
        page = 0

        while page < 3:
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

                yield make_lead_record(
                    empresa=details.get("name", place.get("name", "")),
                    rubro="Tienda Holística / Sahumerios",
                    direccion=details.get("formatted_address", ""),
                    ciudad=_extract_city(addr_comps),
                    provincia=_extract_province(addr_comps),
                    telefono=phone,
                    website=website,
                    google_maps_url=details.get("url", ""),
                    rating=details.get("rating"),
                    reviews_count=details.get("user_ratings_total"),
                    price_level=details.get("price_level"),
                    horarios="; ".join(details.get("opening_hours", {}).get("weekday_text", [])),
                    instagram=_infer_instagram(place.get("name", ""), website),
                    whatsapp=phone.replace(" ", "").replace("-", "").replace("+", "") if phone else "",
                    fuente="Google Places API",
                    tipo_cliente=tipo_cliente,
                )

            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break
            page += 1

        time.sleep(0.5)

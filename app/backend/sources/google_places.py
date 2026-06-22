"""Google Places API (New) source — Text Search.

Relocated from `routers/scraper.py`; migrated from the legacy
`maps.googleapis.com/maps/api/place/*` endpoints to the New Places API
(`places.googleapis.com/v1/places:searchText`), since Google rejects legacy
endpoint calls for projects that only have "Places API (New)" enabled
(the default for newly created keys). A field mask on the Text Search call
returns enough place detail directly, so the separate Place Details request
is no longer needed. Requires a Google Cloud Places API key with billing
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
    (bad/missing key, API not enabled, quota exceeded, etc)."""


PLACES_NEW_BASE = "https://places.googleapis.com/v1"

_SEARCH_FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.addressComponents",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.priceLevel",
    "places.regularOpeningHours",
    "places.googleMapsUri",
    "places.types",
    "nextPageToken",
])

_PRICE_LEVEL_TO_INT = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


def _price_level_to_int(value: Optional[str]) -> Optional[int]:
    """Maps the New API's string price-level enum back to the int 0-4 the
    `leads.price_level` column expects (unmapped/unspecified -> None)."""
    return _PRICE_LEVEL_TO_INT.get(value or "")


def _places_text_search(api_key: str, query: str, page_token: Optional[str] = None) -> dict:
    url = f"{PLACES_NEW_BASE}/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": _SEARCH_FIELD_MASK,
    }
    body: dict = {
        "textQuery": query,
        "languageCode": "es",
        "regionCode": "AR",
    }
    if page_token:
        body["pageToken"] = page_token

    with httpx.Client(timeout=15) as client:
        resp = client.post(url, headers=headers, json=body)

    if resp.status_code != 200:
        try:
            message = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            message = resp.text
        raise PlacesAPIError(f"{resp.status_code}: {message}")

    return resp.json()


def _extract_province(address_components: list) -> str:
    for comp in address_components:
        if "administrative_area_level_1" in comp.get("types", []):
            return comp.get("longText", "")
    return ""


def _extract_city(address_components: list) -> str:
    for comp in address_components:
        if "locality" in comp.get("types", []):
            return comp.get("longText", "")
    return ""


def _infer_instagram(name: str, website: str = "") -> str:
    if website and "instagram.com" in website:
        return website
    slug = re.sub(r"[^a-z0-9]", "", name.lower().replace(" ", ""))
    return f"@{slug[:20]}"


def search_by_name(empresa: str, ciudad: str = "", provincia: str = "") -> Optional[dict]:
    """Cross-references a lead against Google Places via Text Search for its
    name + location, for use during enrichment. There's no per-request API
    key in that pipeline (it runs in a background worker), so this reads
    `settings.GOOGLE_API_KEY` directly — and no-ops without a network call
    if that's unset, so it's safe to include unconditionally."""
    from config import settings

    api_key = settings.GOOGLE_API_KEY
    if not api_key or not empresa:
        return None

    query = " ".join(filter(None, [empresa, ciudad, provincia]))
    try:
        data = _places_text_search(api_key, query)
    except Exception:
        return None

    places = data.get("places", [])
    if not places:
        return None

    place = places[0]
    addr_comps = place.get("addressComponents", [])
    phone = place.get("nationalPhoneNumber", "") or place.get("internationalPhoneNumber", "")
    website = place.get("websiteUri", "")
    name = place.get("displayName", {}).get("text") or empresa

    return {
        "empresa": name,
        "direccion": place.get("formattedAddress", ""),
        "ciudad": _extract_city(addr_comps) or ciudad,
        "provincia": _extract_province(addr_comps) or provincia,
        "telefono": phone,
        "website": website,
        "google_maps_url": place.get("googleMapsUri", ""),
        "instagram": _infer_instagram(name, website),
        "whatsapp": phone.replace(" ", "").replace("-", "").replace("+", "") if phone else "",
    }


@register_source("google_places")
def iter_leads(
    *,
    api_key: str,
    queries: Optional[List[str]] = None,
    tipo_cliente: str = "lead",
    max_per_query: int = 60,
    **_kwargs,
) -> Iterator[dict]:
    """Yields lead records from the Google Places API (New) Text Search.

    Same pagination/delay behavior as the original inline implementation:
    up to 3 pages per query, 2s delay between pages, 0.5s delay between
    queries. The New API's field mask returns enough place detail directly
    from Text Search, so the separate Place Details call is no longer made.
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
            places = data.get("places", [])

            for place in places:
                pid = place.get("id")
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)

                place_types = set(place.get("types", []))
                if place_types & IRRELEVANT_PLACE_TYPES:
                    continue

                addr_comps = place.get("addressComponents", [])
                phone = place.get("nationalPhoneNumber", "") or place.get("internationalPhoneNumber", "")
                website = place.get("websiteUri", "")
                name = place.get("displayName", {}).get("text") or ""

                yield make_lead_record(
                    empresa=name,
                    rubro="Tienda Holística / Sahumerios",
                    direccion=place.get("formattedAddress", ""),
                    ciudad=_extract_city(addr_comps),
                    provincia=_extract_province(addr_comps),
                    telefono=phone,
                    website=website,
                    google_maps_url=place.get("googleMapsUri", ""),
                    rating=place.get("rating"),
                    reviews_count=place.get("userRatingCount"),
                    price_level=_price_level_to_int(place.get("priceLevel")),
                    horarios="; ".join(place.get("regularOpeningHours", {}).get("weekdayDescriptions", [])),
                    instagram=_infer_instagram(name, website),
                    whatsapp=phone.replace(" ", "").replace("-", "").replace("+", "") if phone else "",
                    fuente="Google Places API",
                    tipo_cliente=tipo_cliente,
                )

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            page += 1

        time.sleep(0.5)

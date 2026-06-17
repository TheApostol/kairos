"""Shared rubro/keyword/geo target definitions for the multi-source lead scraper.

Centralizes the wellness/holistic/esoteric "rubro" vocabulary and the
geographic targets (Argentina, prioritizing major commercial cities) used to
build queries for the different free data sources.
"""

# ─────────────────────────────────────────────
# Rubro keywords (wellness / natural / esoteric / decor niche)
# ─────────────────────────────────────────────

RUBRO_KEYWORDS = [
    "dietética", "dietéticas", "herboristería", "herboristerías",
    "casa naturista", "almacén natural", "productos naturales",
    "tienda natural", "tienda saludable", "tienda holística",
    "centro holístico", "casa esotérica", "tienda esotérica",
    "santería", "sahumerios", "aromaterapia", "velas", "cristales",
    "minerales", "reiki", "yoga", "meditación", "bienestar",
    "feng shui", "regalería", "decoración boho", "decoración espiritual",
]

COMMERCIAL_VARIANTS = [
    "mayorista", "minorista", "distribuidora", "local", "tienda",
    "comercio", "proveedor", "venta al público", "venta mayorista",
]


# ─────────────────────────────────────────────
# Geographic targets — Argentina, prioritizing major commercial cities
# ─────────────────────────────────────────────
# `pa_slug` is the lowercase/no-accent slug used by paginasamarillas.com.ar
# location-based listing URLs (`/b/{categoria}/{pa_slug}`).

GEO_TARGETS = [
    {"name": "CABA", "provincia": "Ciudad Autónoma de Buenos Aires", "pa_slug": "buenos-aires"},
    {"name": "GBA Norte", "provincia": "Buenos Aires", "pa_slug": "san-isidro"},
    {"name": "GBA Sur", "provincia": "Buenos Aires", "pa_slug": "avellaneda"},
    {"name": "GBA Oeste", "provincia": "Buenos Aires", "pa_slug": "moron"},
    {"name": "La Plata", "provincia": "Buenos Aires", "pa_slug": "la-plata"},
    {"name": "Mar del Plata", "provincia": "Buenos Aires", "pa_slug": "mar-del-plata"},
    {"name": "Bahía Blanca", "provincia": "Buenos Aires", "pa_slug": "bahia-blanca"},
    {"name": "Rosario", "provincia": "Santa Fe", "pa_slug": "rosario"},
    {"name": "Córdoba", "provincia": "Córdoba", "pa_slug": "cordoba"},
    {"name": "Mendoza", "provincia": "Mendoza", "pa_slug": "mendoza"},
    {"name": "Tucumán", "provincia": "Tucumán", "pa_slug": "san-miguel-de-tucuman"},
    {"name": "Salta", "provincia": "Salta", "pa_slug": "salta"},
    {"name": "Santa Fe", "provincia": "Santa Fe", "pa_slug": "santa-fe"},
    {"name": "Paraná", "provincia": "Entre Ríos", "pa_slug": "parana"},
    {"name": "Neuquén", "provincia": "Neuquén", "pa_slug": "neuquen"},
    {"name": "Bariloche", "provincia": "Río Negro", "pa_slug": "bariloche"},
    {"name": "San Juan", "provincia": "San Juan", "pa_slug": "san-juan"},
    {"name": "San Luis", "provincia": "San Luis", "pa_slug": "san-luis"},
    {"name": "Corrientes", "provincia": "Corrientes", "pa_slug": "corrientes"},
    {"name": "Resistencia", "provincia": "Chaco", "pa_slug": "resistencia"},
    {"name": "Posadas", "provincia": "Misiones", "pa_slug": "posadas"},
    {"name": "Jujuy", "provincia": "Jujuy", "pa_slug": "jujuy"},
    {"name": "Santiago del Estero", "provincia": "Santiago del Estero", "pa_slug": "santiago-del-estero"},
    {"name": "Comodoro Rivadavia", "provincia": "Chubut", "pa_slug": "comodoro-rivadavia"},
    {"name": "Río Gallegos", "provincia": "Santa Cruz", "pa_slug": "rio-gallegos"},
    {"name": "Ushuaia", "provincia": "Tierra del Fuego", "pa_slug": "ushuaia"},
]


# ─────────────────────────────────────────────
# OpenStreetMap / Overpass targets
# ─────────────────────────────────────────────
# Bounding boxes (south, west, north, east) for the biggest commercial
# cities. Kept to a manageable set since each bbox = one Overpass request.

OVERPASS_BBOXES = {
    "CABA": (-34.705, -58.531, -34.526, -58.335),
    "GBA Norte": (-34.50, -58.56, -34.40, -58.45),       # San Isidro area
    "GBA Sur": (-34.71, -58.42, -34.61, -58.31),         # Avellaneda area
    "GBA Oeste": (-34.70, -58.68, -34.60, -58.56),       # Morón area
    "Córdoba": (-31.493, -64.273, -31.317, -64.083),
    "Rosario": (-33.02, -60.75, -32.86, -60.60),
    "Mendoza": (-32.97, -68.92, -32.84, -68.78),
    "La Plata": (-34.97, -58.05, -34.86, -57.90),
    "Mar del Plata": (-38.05, -57.62, -37.95, -57.50),
    "Bahía Blanca": (-38.76, -62.32, -38.68, -62.21),
    "Tucumán": (-26.86, -65.27, -26.78, -65.18),
    "Salta": (-24.81, -65.45, -24.74, -65.36),
    "Santa Fe": (-31.68, -60.75, -31.58, -60.63),
    "Paraná": (-31.77, -60.57, -31.69, -60.48),
    "Neuquén": (-38.99, -68.10, -38.92, -68.00),
    "Bariloche": (-41.17, -71.38, -41.10, -71.25),
    "San Juan": (-31.58, -68.59, -31.50, -68.48),
    "San Luis": (-33.33, -66.39, -33.26, -66.28),
    "Corrientes": (-27.52, -58.88, -27.44, -58.79),
    "Resistencia": (-27.49, -59.04, -27.41, -58.94),
    "Posadas": (-27.41, -55.96, -27.32, -55.85),
    "Jujuy": (-24.23, -65.34, -24.14, -65.26),
    "Santiago del Estero": (-27.84, -64.31, -27.75, -64.21),
    "Comodoro Rivadavia": (-45.91, -67.55, -45.82, -67.43),
    "Río Gallegos": (-51.66, -69.27, -51.58, -69.16),
    "Ushuaia": (-54.84, -68.36, -54.77, -68.25),
}

# Shop/amenity tags relevant to the wellness/natural/esoteric niche.
OVERPASS_TAGS = [
    {"shop": "herbalist"},
    {"shop": "health_food"},
    {"shop": "esoteric"},
    {"shop": "variety_store"},
    {"shop": "houseware"},
    {"amenity": "yoga"},
    {"shop": "yoga"},
    {"leisure": "yoga"},
]


# ─────────────────────────────────────────────
# datos.jus.gob.ar "Registro Nacional de Sociedades" relevance filter
# ─────────────────────────────────────────────
# CLAE 2020 4-digit divisions whose businesses are plausibly relevant to the
# wellness/natural/esoteric/decor niche (only ~12% of RNS rows carry an
# actividad_codigo at all, so this is a secondary signal — name-based
# keyword matching below is the primary one).

RNS_RELEVANT_CLAE_PREFIXES = ["4773", "4775", "4649", "4761", "8552", "9609"]

RNS_RELEVANT_KEYWORDS = [
    "dietetic", "herboris", "naturista", "esoteric", "sahumerio", "inciens",
    "aromaterap", "yoga", "reiki", "cristal", "velas", "holistic",
    "bienestar", "feng shui", "meditacion", "meditación", "natural",
    "santeria", "santería",
]


# ─────────────────────────────────────────────
# Páginas Amarillas Argentina — category slugs for `/b/{slug}/{location}`
# ─────────────────────────────────────────────
# Confirmed live (returned `total` > 0 for at least one major city). Slugs
# not in this map are skipped — paginasamarillas returns `total: 0` rather
# than an error for unknown categories, but we avoid the wasted requests.

RUBRO_TO_PA_SLUGS: dict[str, str] = {
    "Dietética": "dieteticas",
    "Herboristería": "herboristerias",
    "Casa Naturista": "casas-naturistas",
    "Almacén Natural": "almacenes-naturistas",
    "Productos Naturales": "productos-naturales",
    "Centro Holístico": "centros-holisticos",
    "Casa Esotérica": "casas-esotericas",
    "Santería": "santerias",
    "Sahumerios": "venta-de-sahumerios",
    "Aromaterapia": "aromaterapia",
    "Velas": "velas",
    "Cristales": "cristales",
    "Minerales": "minerales",
    "Reiki": "reiki",
    "Yoga": "yoga",
    "Centro de Yoga": "centros-de-yoga",
    "Meditación": "meditacion",
    "Feng Shui": "feng-shui",
    "Regalería": "regalerias",
    "Decoración": "decoracion",
}


def build_freetext_queries(geo_targets=None, rubro_pa_slugs=None) -> list[tuple[str, str, str]]:
    """Builds (rubro_label, category_slug, location_slug) combos for
    paginasamarillas.com.ar listing pages (`/b/{category_slug}/{location_slug}`).

    Pairs every rubro category with every geo target — Páginas Amarillas
    returns `total: 0` for empty combos so this is safe, just bounded by
    `max_records`/pagination limits in the source module itself.
    """
    geos = geo_targets if geo_targets is not None else GEO_TARGETS
    rubros = rubro_pa_slugs if rubro_pa_slugs is not None else RUBRO_TO_PA_SLUGS

    combos = []
    for rubro_label, category_slug in rubros.items():
        for geo in geos:
            combos.append((rubro_label, category_slug, geo["pa_slug"]))
    return combos

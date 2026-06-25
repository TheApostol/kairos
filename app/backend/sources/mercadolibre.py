"""MercadoLibre public search API source.

Finds wholesale-buyer leads by searching MercadoLibre for holistic/esoteric
products and surfacing sellers with an established sales history (20+
transactions) — these are typically small businesses already reselling this
kind of merchandise, making them good mayorista targets. Free, keyless API.
"""

import time
from typing import Iterator

import httpx

from services.scraping_utils import RateLimiter, make_lead_record
from . import register_source

SEARCH_URL = "https://api.mercadolibre.com/sites/MLA/search"
USER_URL = "https://api.mercadolibre.com/users/{seller_id}"

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

MIN_TRANSACTIONS = 20

_rate_limiter = RateLimiter(min_interval=0.4, jitter=0.2)


@register_source("mercadolibre")
def iter_leads(*, queries: list[str] = None, tipo_cliente: str = "mayorista", **_kwargs) -> Iterator[dict]:
    """Yields one lead per established MercadoLibre seller (20+ transactions)
    found across a search-by-product-keyword sweep."""
    seen_sellers: set = set()

    with httpx.Client(timeout=15) as client:
        for query in queries or ML_PRODUCT_QUERIES:
            for offset in (0, 50):
                _rate_limiter.wait()
                try:
                    resp = client.get(SEARCH_URL, params={"q": query, "limit": 50, "offset": offset})
                    if resp.status_code != 200:
                        continue
                    results = resp.json().get("results", [])
                except Exception:
                    continue

                for item in results:
                    seller = item.get("seller", {})
                    seller_id = seller.get("id")
                    if not seller_id or seller_id in seen_sellers:
                        continue
                    seen_sellers.add(seller_id)

                    transactions = (seller.get("seller_reputation", {}).get("transactions", {}) or {}).get("total", 0)
                    if transactions < MIN_TRANSACTIONS:
                        continue

                    nickname = seller.get("nickname") or f"ML-{seller_id}"
                    permalink = f"https://www.mercadolibre.com.ar/perfil/{nickname}"

                    city, state = "", ""
                    try:
                        time.sleep(0.1)
                        det = client.get(USER_URL.format(seller_id=seller_id))
                        if det.status_code == 200:
                            address = det.json().get("address") or {}
                            city = address.get("city", "") or ""
                            state = address.get("state", "") or ""
                    except Exception:
                        pass

                    yield make_lead_record(
                        empresa=nickname,
                        rubro="Vendedor MercadoLibre",
                        ciudad=city,
                        provincia=state,
                        website=permalink,
                        fuente="MercadoLibre API",
                        observaciones=f"Ventas ML: {transactions}",
                        tipo_cliente=tipo_cliente,
                    )

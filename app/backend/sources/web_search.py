"""General web-search lead discovery via DuckDuckGo HTML search.

Unlike the directory-style sources (green-life, Páginas Amarillas, etc.)
this casts a wide net across the open web: it runs "{rubro} en {ciudad}"
style searches built from the shared rubro/geo vocabulary and turns
plausible business-website results into lead records — useful for niches
or areas not covered by the fixed directories.
"""

import re
from typing import Iterator, Optional

from constants.scraper_targets import GEO_TARGETS, RUBRO_KEYWORDS
from services.scraping_utils import ddg_html_search, make_lead_record
from . import register_source

_DOMAIN_REGEX = re.compile(r"(https?://[^/]+)")

_TITLE_SUFFIX_REGEX = re.compile(
    r"\s*[-|–]\s*(Facebook|Instagram|Inicio|Home|Página principal).*$",
    re.IGNORECASE,
)


def _clean_title(title: str) -> str:
    return _TITLE_SUFFIX_REGEX.sub("", title).strip()


def _build_queries(rubros: list[str], geos: list[dict]) -> Iterator[tuple[str, dict]]:
    """Pairs each geo target with one rubro at a time, rotating through
    `rubros` so a full run covers the whole keyword list without an
    O(rubros*geos) explosion of search requests."""
    for i, geo in enumerate(geos):
        rubro = rubros[i % len(rubros)]
        yield rubro, geo


@register_source("web_search")
def iter_leads(
    *,
    tipo_cliente: str = "lead",
    max_per_query: int = 6,
    rubros: Optional[list[str]] = None,
    geos: Optional[list[dict]] = None,
    **_kwargs,
) -> Iterator[dict]:
    """Yields lead records from DuckDuckGo web-search results for
    "{rubro} en {ciudad}, Argentina" style queries."""
    rubros = rubros if rubros is not None else RUBRO_KEYWORDS
    geos = geos if geos is not None else GEO_TARGETS

    seen_domains: set[str] = set()

    for rubro, geo in _build_queries(rubros, geos):
        ciudad = geo["name"]
        provincia = geo["provincia"]
        query = f"{rubro} en {ciudad}, Argentina"

        for result in ddg_html_search(query, max_results=max_per_query):
            m = _DOMAIN_REGEX.match(result["url"])
            domain = m.group(1) if m else result["url"]
            if domain in seen_domains:
                continue
            seen_domains.add(domain)

            empresa = _clean_title(result["title"]) or domain
            yield make_lead_record(
                empresa=empresa,
                rubro=rubro.title(),
                ciudad=ciudad,
                provincia=provincia,
                website=domain,
                observaciones=result["snippet"],
                fuente="Búsqueda web (DuckDuckGo)",
                tipo_cliente=tipo_cliente,
                ficha_url=result["url"],
            )

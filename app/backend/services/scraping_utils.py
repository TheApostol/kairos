"""Shared helpers for the free/public-data lead scraper sources.

Provides a consistent User-Agent, rate limiting, retrying HTTP fetches,
optional raw-response dumps for debugging, a standard lead-record builder,
and free website discovery via DuckDuckGo HTML search.
"""

import os
import random
import re
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup

USER_AGENT = (
    "KairosLeadBot/1.0 (+https://kairos.polkorp.com; "
    "contacto@kairos.polkorp.com; CRM lead discovery for wellness/natural "
    "retailers in Argentina)"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "es-AR,es;q=0.9",
}

# Optional debug dumps of raw responses, for inspecting source pages while
# developing/debugging a scraper without re-running the whole job.
SCRAPER_DEBUG_DUMP = os.environ.get("SCRAPER_DEBUG_DUMP", "").lower() in ("1", "true", "yes")
SCRAPER_DEBUG_DIR = os.environ.get("SCRAPER_DEBUG_DIR", "/tmp/kairos_scraper_dumps")


def _debug_dump(url: str, content: bytes) -> None:
    if not SCRAPER_DEBUG_DUMP:
        return
    try:
        os.makedirs(SCRAPER_DEBUG_DIR, exist_ok=True)
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", url)[-150:]
        path = os.path.join(SCRAPER_DEBUG_DIR, f"{slug}.dump")
        with open(path, "wb") as f:
            f.write(content)
    except Exception:
        pass


class RateLimiter:
    """Sleeps as needed to keep requests at least `min_interval` seconds
    apart (plus optional random jitter), per source."""

    def __init__(self, min_interval: float = 1.0, jitter: float = 0.0):
        self.min_interval = min_interval
        self.jitter = jitter
        self._last_request: float = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request
        delay = self.min_interval - elapsed
        if self.jitter:
            delay += random.uniform(0, self.jitter)
        if delay > 0:
            time.sleep(delay)
        self._last_request = time.monotonic()


def fetch_with_retries(
    url: str,
    method: str = "GET",
    *,
    rate_limiter: Optional[RateLimiter] = None,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    data=None,
    json=None,
    timeout: float = 30,
    max_retries: int = 3,
    backoff_base: float = 1.5,
) -> Optional[httpx.Response]:
    """GET/POST with exponential backoff on timeouts/429/5xx.

    Returns the response (which may have a non-2xx status if all retries
    were exhausted with a non-retryable error) or None if every attempt
    raised a transport-level exception.
    """
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}

    for attempt in range(max_retries):
        if rate_limiter:
            rate_limiter.wait()
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.request(
                    method, url, headers=merged_headers, params=params, data=data, json=json
                )
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt == max_retries - 1:
                return None
            time.sleep(backoff_base ** attempt)
            continue

        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == max_retries - 1:
                return resp
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = backoff_base ** attempt
            else:
                delay = backoff_base ** attempt
            time.sleep(delay)
            continue

        _debug_dump(url, resp.content)
        return resp

    return None


def make_lead_record(
    *,
    empresa: str,
    rubro: str = "",
    direccion: str = "",
    ciudad: str = "",
    provincia: str = "",
    telefono: str = "",
    website: str = "",
    google_maps_url: str = "",
    rating=None,
    reviews_count=None,
    price_level=None,
    horarios: str = "",
    instagram: str = "",
    email: str = "",
    whatsapp: str = "",
    observaciones: str = "",
    fuente: str = "",
    estado: str = "nuevo",
    tipo_cliente: str = "lead",
    ficha_url: str = "",
) -> dict:
    """Builds a lead dict matching the `leads` table shape. `ficha_url`
    (the source's detail-page URL, if any) is appended to `observaciones`
    since `leads` has no dedicated source-URL column."""

    if ficha_url:
        observaciones = f"{observaciones} | Ficha: {ficha_url}".strip(" |") if observaciones else f"Ficha: {ficha_url}"

    return {
        "empresa": empresa,
        "rubro": rubro,
        "direccion": direccion,
        "ciudad": ciudad,
        "provincia": provincia,
        "telefono": telefono,
        "website": website,
        "google_maps_url": google_maps_url,
        "rating": rating,
        "reviews_count": reviews_count,
        "price_level": price_level,
        "horarios": horarios,
        "instagram": instagram,
        "email": email,
        "whatsapp": whatsapp,
        "observaciones": observaciones,
        "fuente": fuente,
        "fecha_extraccion": datetime.now(timezone.utc).date().isoformat(),
        "estado": estado,
        "tipo_cliente": tipo_cliente,
    }


# ─────────────────────────────────────────────
# Free website/lead discovery via DuckDuckGo HTML search
# ─────────────────────────────────────────────

EXCLUDED_DOMAINS = (
    "facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com",
    "linkedin.com", "youtube.com", "whatsapp.com", "wa.me",
    "paginasamarillas.com.ar", "guiacomerciales.com", "green-life.com.ar",
    "ecored.org", "mercadolibre.com", "mercadolibre.com.ar",
    "maps.google.com", "google.com", "goo.gl",
    "openstreetmap.org", "datos.jus.gob.ar", "duckduckgo.com",
)

# DDG's HTML endpoint anti-bot checks are picky about looking like a real
# browser — a generic identifying UA gets a 202 "anomaly" response.
DDG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/x-www-form-urlencoded",
}

_DDG_REDIRECT_URL_REGEX = re.compile(r"uddg=([^&]+)")

_ddg_rate_limiter = RateLimiter(min_interval=1.0, jitter=1.0)


def ddg_html_search(query: str, max_results: int = 8) -> list[dict]:
    """Free web search via DuckDuckGo's HTML endpoint (no API key).

    Returns up to `max_results` results as `{"title", "url", "snippet"}`
    dicts, filtering out directories/social networks/map services (see
    `EXCLUDED_DOMAINS`). Best-effort: returns `[]` if DDG rate-limits/blocks
    the request or no results survive the filter.
    """
    resp = fetch_with_retries(
        "https://html.duckduckgo.com/html/",
        method="POST",
        rate_limiter=_ddg_rate_limiter,
        data={"q": query},
        headers=DDG_HEADERS,
        timeout=15,
        max_retries=2,
    )
    if resp is None or resp.status_code != 200:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    for result in soup.select("div.result"):
        link = result.select_one("a.result__a")
        if not link:
            continue

        href = link.get("href", "")
        url = href
        m = _DDG_REDIRECT_URL_REGEX.search(href)
        if m:
            url = unquote(m.group(1))

        if not url.startswith("http"):
            continue
        if any(domain in url for domain in EXCLUDED_DOMAINS):
            continue

        title = link.get_text(" ", strip=True)
        snippet_el = result.select_one("a.result__snippet, .result__snippet")
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

        results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= max_results:
            break

    return results


def discover_website_ddg(empresa: str, ciudad: str = "", provincia: str = "") -> str:
    """Free website discovery via DuckDuckGo's HTML endpoint (no API key).

    Returns the first plausible business website (filtering out directories,
    social networks, and map services), or "" if nothing useful is found
    (including if DDG rate-limits/blocks the request — this is best-effort).
    """
    if not empresa:
        return ""

    query_parts = [empresa, ciudad, provincia, "Argentina"]
    query = " ".join(p for p in query_parts if p)

    for result in ddg_html_search(query, max_results=5):
        # Strip to scheme://host for a clean "website" field
        m = re.match(r"(https?://[^/]+)", result["url"])
        if m:
            return m.group(1)

    return ""

"""Facebook public-page cross-reference source.

Like `sources/instagram.py`, this only exposes `search_by_name` for the
enrichment cross-reference pass — Facebook has no public lead-discovery
search, but a business's own About page (when public) often lists a phone,
email and website that the mobile site renders without requiring login.
"""

import re
from typing import Optional

from services.scraping_utils import (
    EMAIL_REGEX,
    EXCLUDED_DOMAINS,
    GENERIC_BUSINESS_WORDS,
    PHONE_TEXT_REGEX,
    RateLimiter,
    ddg_html_search,
    fetch_with_retries,
    is_valid_email,
    name_tokens,
)

_rate_limiter = RateLimiter(min_interval=2.0, jitter=1.0)

_MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15",
    "Accept-Language": "es-AR,es;q=0.9",
}


def _mine_text(text: str) -> dict:
    found = {"email": "", "telefono": ""}
    emails = [e for e in EMAIL_REGEX.findall(text) if is_valid_email(e)]
    if emails:
        found["email"] = emails[0]
    m = PHONE_TEXT_REGEX.search(text)
    if m and len(re.sub(r"\D", "", m.group())) >= 8:
        found["telefono"] = m.group().strip()
    return found


def _scrape_about_page(fb_url: str) -> dict:
    """Best-effort scrape of a Facebook page's mobile About section
    (`m.facebook.com/.../?v=info`), which renders without login for public
    pages. Degrades to empty fields on any failure (private page, layout
    change, rate limit) rather than raising."""
    result = {"email": "", "telefono": "", "website": ""}
    mobile_url = re.sub(r"^https?://(www\.)?facebook\.com", "https://m.facebook.com", fb_url).rstrip("/") + "/?v=info"
    resp = fetch_with_retries(mobile_url, rate_limiter=_rate_limiter, headers=_MOBILE_HEADERS, timeout=10, max_retries=1)
    if resp is None or resp.status_code != 200:
        return result

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "html.parser")

    for field, value in _mine_text(soup.get_text(" ")).items():
        if value:
            result[field] = value

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and "facebook.com" not in href:
            domain = href.split("/")[2].lower().replace("www.", "")
            if domain and not any(d in domain for d in EXCLUDED_DOMAINS):
                result["website"] = href.split("?")[0].rstrip("/")
                break

    return result


def search_by_name(empresa: str, ciudad: str = "", provincia: str = "") -> Optional[dict]:
    """Cross-references a lead against Facebook the same way
    `sources/instagram.py` does: a name-verified `site:facebook.com`
    DuckDuckGo search, then a best-effort scrape of the page's mobile About
    section for whatever contact fields are still missing.
    """
    if not empresa:
        return None

    location = " ".join(p for p in (ciudad, provincia) if p)
    query = f'site:facebook.com "{empresa}" {location} Argentina'.strip()
    allowed_domains = tuple(d for d in EXCLUDED_DOMAINS if d != "facebook.com")
    empresa_tokens = name_tokens(empresa) - GENERIC_BUSINESS_WORDS

    fb_url = ""
    snippet_hit: dict = {}
    for result in ddg_html_search(query, max_results=5, excluded_domains=allowed_domains):
        if "facebook.com/" not in result["url"]:
            continue
        if empresa_tokens and not (empresa_tokens & (name_tokens(result.get("title", "")) - GENERIC_BUSINESS_WORDS)):
            continue
        fb_url = result["url"]
        snippet_hit = _mine_text(result.get("title", "") + " " + result.get("snippet", ""))
        break

    if not fb_url:
        return None

    found = {}
    for field, value in snippet_hit.items():
        if value:
            found[field] = value

    about = _scrape_about_page(fb_url)
    for field in ("email", "telefono", "website"):
        if about.get(field) and not found.get(field):
            found[field] = about[field]

    return found or None

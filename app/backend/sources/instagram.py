"""Instagram public-profile cross-reference source.

Instagram has no public lead-discovery search/directory, so this module
exposes only `search_by_name` — used by the enrichment cross-reference pass
(see `routers/scraper.py`'s `_CROSS_REFERENCE_SOURCES`) to fill in whatever
contact fields are still missing for an existing lead, by finding its
Instagram profile via a name-verified DuckDuckGo search and reading the
public bio (and, if the bio links to a Linktree/bio.link-style aggregator,
following that too).
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

_IG_HANDLE_REGEX = re.compile(r"instagram\.com/([A-Za-z0-9._]{1,30})")
_IG_RESERVED_PATHS = {"p", "reel", "reels", "stories", "explore", "accounts", "tv", "directory"}

_LINK_AGGREGATOR_DOMAINS = ("linktr.ee", "linktree.com", "bio.link", "beacons.ai", "taplink.cc", "campsite.bio")

_rate_limiter = RateLimiter(min_interval=2.0, jitter=1.0)

_MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15",
    "Accept-Language": "es-AR,es;q=0.9",
}


def _extract_handle(url: str) -> str:
    m = _IG_HANDLE_REGEX.search(url)
    if not m:
        return ""
    handle = m.group(1)
    return "" if handle.lower() in _IG_RESERVED_PATHS else handle


def _mine_text(text: str) -> dict:
    found = {"email": "", "telefono": ""}
    emails = [e for e in EMAIL_REGEX.findall(text) if is_valid_email(e)]
    if emails:
        found["email"] = emails[0]
    m = PHONE_TEXT_REGEX.search(text)
    if m and len(re.sub(r"\D", "", m.group())) >= 8:
        found["telefono"] = m.group().strip()
    return found


def _follow_aggregator(url: str) -> dict:
    """Follows a Linktree/bio.link-style aggregator page (commonly linked
    from an Instagram bio in lieu of a direct website) and collects whatever
    contact links it lists."""
    result = {"website": "", "email": "", "telefono": "", "whatsapp": ""}
    resp = fetch_with_retries(url, rate_limiter=_rate_limiter, headers=_MOBILE_HEADERS, timeout=10, max_retries=1)
    if resp is None or resp.status_code != 200:
        return result

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:") and not result["email"]:
            candidate = href.split("mailto:")[-1].split("?")[0].strip()
            if is_valid_email(candidate):
                result["email"] = candidate
        elif ("wa.me" in href or "whatsapp.com" in href) and not result["whatsapp"]:
            digits = re.sub(r"\D", "", href.split("wa.me/")[-1] if "wa.me" in href else href)
            if len(digits) >= 8:
                result["whatsapp"] = digits
        elif href.startswith("http") and not result["website"]:
            domain = href.split("/")[2].lower().replace("www.", "")
            if domain and not any(d in domain for d in EXCLUDED_DOMAINS) and not any(
                d in domain for d in _LINK_AGGREGATOR_DOMAINS
            ):
                result["website"] = href.split("?")[0].rstrip("/")

    if not result["email"] or not result["telefono"]:
        mined = _mine_text(soup.get_text(" "))
        result["email"] = result["email"] or mined["email"]
        result["telefono"] = result["telefono"] or mined["telefono"]

    return result


def _scrape_profile(handle: str) -> dict:
    """Best-effort scrape of a public Instagram profile's bio (the
    `og:description` meta tag) and external link, without requiring login.
    Instagram aggressively rate-limits/blocks scraping, so this degrades to
    empty fields on any failure rather than raising — same posture as
    `routers/scraper.py`'s `_scrape_website`."""
    result = {"email": "", "telefono": "", "website": ""}
    resp = fetch_with_retries(
        f"https://www.instagram.com/{handle}/",
        rate_limiter=_rate_limiter,
        headers=_MOBILE_HEADERS,
        timeout=10,
        max_retries=1,
    )
    if resp is None or resp.status_code != 200:
        return result

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "html.parser")

    og = soup.find("meta", attrs={"property": "og:description"})
    if og:
        # og:description reads like "1,234 Followers, 56 Following - <bio text>"
        bio = re.sub(r"^[\d,]+\s*Followers.*?-\s*", "", og.get("content", ""))
        for field, value in _mine_text(bio).items():
            if value:
                result[field] = value

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and "instagram.com" not in href:
            domain = href.split("/")[2].lower().replace("www.", "")
            if domain and not any(d in domain for d in EXCLUDED_DOMAINS):
                result["website"] = href.split("?")[0].rstrip("/")
                break

    return result


def search_by_name(empresa: str, ciudad: str = "", provincia: str = "") -> Optional[dict]:
    """Cross-references a lead against Instagram via a name-verified
    `site:instagram.com` DuckDuckGo search — DDG's own ranking isn't enough
    on its own, since a wrong match would confidently overwrite the lead's
    contact fields with an unrelated business's, so a result is only
    accepted if its title shares a non-generic name token with `empresa`.

    Best-effort end to end: returns whatever was found, even just the
    handle, since every further step (profile scrape, aggregator follow)
    can fail independently without invalidating what came before.
    """
    if not empresa:
        return None

    location = " ".join(p for p in (ciudad, provincia) if p)
    query = f'site:instagram.com "{empresa}" {location} Argentina'.strip()
    allowed_domains = tuple(d for d in EXCLUDED_DOMAINS if d != "instagram.com")
    empresa_tokens = name_tokens(empresa) - GENERIC_BUSINESS_WORDS

    handle = ""
    snippet_hit: dict = {}
    for result in ddg_html_search(query, max_results=5, excluded_domains=allowed_domains):
        if "instagram.com/" not in result["url"]:
            continue
        candidate = _extract_handle(result["url"])
        if not candidate:
            continue
        if empresa_tokens and not (empresa_tokens & (name_tokens(result.get("title", "")) - GENERIC_BUSINESS_WORDS)):
            continue
        handle = candidate
        snippet_hit = _mine_text(result.get("title", "") + " " + result.get("snippet", ""))
        break

    if not handle:
        return None

    found = {"instagram": f"@{handle}"}
    for field, value in snippet_hit.items():
        if value:
            found[field] = value

    profile = _scrape_profile(handle)
    for field in ("email", "telefono"):
        if profile.get(field) and not found.get(field):
            found[field] = profile[field]

    bio_link = profile.get("website", "")
    if bio_link:
        if any(d in bio_link for d in _LINK_AGGREGATOR_DOMAINS):
            agg = _follow_aggregator(bio_link)
            for field in ("website", "email", "telefono", "whatsapp"):
                if agg.get(field) and not found.get(field):
                    found[field] = agg[field]
            if not found.get("website"):
                found["website"] = bio_link
        else:
            found["website"] = bio_link

    return found

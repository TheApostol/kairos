from __future__ import annotations

import re
from typing import Optional

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.auth import OrgContext, get_current_org
from services.audit import write_audit_log
from services.usage import record_usage

router = APIRouter(prefix="/product-intelligence", tags=["product-intelligence"])


class ProductCheckRequest(BaseModel):
    product_id: Optional[str] = None
    sku: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    current_image_url: Optional[str] = None


def _clean(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _build_query(body: ProductCheckRequest) -> str:
    parts = [_clean(body.brand), _clean(body.name), _clean(body.sku)]
    return " ".join([p for p in parts if p])


def _duckduckgo_search(query: str) -> list[dict]:
    if not query:
        return []
    url = "https://duckduckgo.com/html/"
    try:
        with httpx.Client(timeout=12, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
            resp = client.get(url, params={"q": query})
            if resp.status_code != 200:
                return []
            html = resp.text
    except Exception:
        return []

    results: list[dict] = []
    pattern = re.compile(r'<a rel="nofollow" class="result__a" href="(?P<href>[^"]+)">(?P<title>.*?)</a>', re.I | re.S)
    for match in pattern.finditer(html):
        title = re.sub(r"<.*?>", "", match.group("title"))
        href = match.group("href")
        results.append({"title": title.strip(), "url": href})
        if len(results) >= 8:
            break
    return results


def _image_candidates(query: str) -> list[dict]:
    # Lightweight, provider-agnostic image suggestions. This intentionally does
    # not scrape image binary data. It gives operators quick links to verify and
    # manually select the best source/image.
    encoded = query.replace(" ", "+")
    return [
        {"provider": "Google Images", "url": f"https://www.google.com/search?tbm=isch&q={encoded}"},
        {"provider": "Bing Images", "url": f"https://www.bing.com/images/search?q={encoded}"},
        {"provider": "MercadoLibre", "url": f"https://listado.mercadolibre.com.ar/{encoded}"},
        {"provider": "Web search", "url": f"https://www.google.com/search?q={encoded}"},
    ]


@router.post("/check")
def check_product_online(body: ProductCheckRequest, current_org: OrgContext = Depends(get_current_org)):
    query = _build_query(body)
    web_results = _duckduckgo_search(query)
    sku_mentions = [r for r in web_results if body.sku and body.sku.lower() in (r.get("title", "") + " " + r.get("url", "")).lower()]
    name_mentions = [r for r in web_results if body.name and body.name.lower()[:20] in r.get("title", "").lower()]

    confidence = "low"
    if sku_mentions:
        confidence = "high"
    elif name_mentions or len(web_results) >= 3:
        confidence = "medium"

    record_usage(org=current_org, metric="product_checks", quantity=1, source="product_intelligence", entity="product", entity_id=body.product_id)
    write_audit_log(
        org=current_org,
        action="product.check_online",
        entity="product",
        entity_id=body.product_id,
        metadata={"sku": body.sku, "name": body.name, "brand": body.brand, "confidence": confidence, "results": len(web_results)},
    )

    return {
        "query": query,
        "confidence": confidence,
        "sku_match_found": bool(sku_mentions),
        "name_match_found": bool(name_mentions),
        "has_current_image": bool(body.current_image_url),
        "web_results": web_results,
        "image_candidates": _image_candidates(query),
        "recommendation": "SKU appears online" if sku_mentions else "Review manually before updating SKU/image",
    }

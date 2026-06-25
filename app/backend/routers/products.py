import io
import re
import time
from xml.sax.saxutils import escape as _xml_escape
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.auth import OrgContext, get_current_org
from services.supabase_client import db, ScopedSupabaseClient
from services.scraping_utils import ddg_image_search

router = APIRouter(prefix="/products", tags=["products"])


# ─────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────

class ProductCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    categoria: Optional[str] = None
    precio_minorista: Optional[float] = None
    precio_mayorista: Optional[float] = None
    precio_promo: Optional[float] = None
    cantidad_mayorista: Optional[int] = None
    stock: Optional[int] = None
    sku: Optional[str] = None
    imagen_url: Optional[str] = None
    imagenes_extra: Optional[List[str]] = None
    activo: bool = True
    destacado: bool = False
    orden: Optional[int] = None


class ProductUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    categoria: Optional[str] = None
    precio_minorista: Optional[float] = None
    precio_mayorista: Optional[float] = None
    precio_promo: Optional[float] = None
    cantidad_mayorista: Optional[int] = None
    stock: Optional[int] = None
    sku: Optional[str] = None
    imagen_url: Optional[str] = None
    imagenes_extra: Optional[List[str]] = None
    activo: Optional[bool] = None
    destacado: Optional[bool] = None
    orden: Optional[int] = None


class CatalogExportRequest(BaseModel):
    product_ids: Optional[List[str]] = None
    titulo: str = "Catálogo de Productos"
    incluir_precios: bool = True


# ─────────────────────────────────────────────
# PDF CATALOG GENERATOR
# ─────────────────────────────────────────────

def _pdf_text(value) -> str:
    """Escape text for ReportLab Paragraph's XML-like markup.

    Product names/descriptions/categories often contain '&', '<', '>' which
    Paragraph's parser otherwise chokes on, breaking the whole PDF build.
    """
    return _xml_escape(str(value)) if value else ""


_IMAGE_FETCH_HEADERS = {
    # Several product images are hosted behind a CDN (CloudFront) that
    # returns 403 for requests with no/non-browser User-Agent — confirmed
    # via direct testing (httpx's default "python-httpx/x.y.z" UA gets
    # blocked, a browser-like one doesn't). Without this, every image
    # silently failed to fetch and no catalog ever had images.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}


def _decoded_image_bytes(content: bytes) -> Optional[bytes]:
    """Verifies `content` is decodable image data, then downscales it to the
    size actually rendered in the PDF (products are embedded at 3cm). Product
    photos straight from the source CDN can be several MB at full resolution
    — embedding ~500 of those unresized produced 150MB+ PDFs that took over a
    minute to build and reliably failed to download/open. `reportlab.platypus.
    Image` only decodes lazily at `doc.build()` time — by then there's no
    try/except around it, so a single corrupt/non-image response (e.g. a
    CDN's 200 OK HTML error page) would crash the *entire* catalog export
    instead of just skipping that one image."""
    try:
        from PIL import Image as PILImage
        import io as _io
        with PILImage.open(_io.BytesIO(content)) as img:
            img.verify()
        # verify() invalidates the image for further use, so re-open fresh.
        with PILImage.open(_io.BytesIO(content)) as img:
            img = img.convert("RGB")
            img.thumbnail((400, 400))
            out = _io.BytesIO()
            img.save(out, format="JPEG", quality=75)
            return out.getvalue()
    except Exception:
        return None


def _prefetch_images(urls: set, overall_timeout: float = 20.0) -> dict:
    """Downloads unique http(s) product image URLs concurrently, within a
    fixed overall time budget.

    A full catalog can have hundreds of products, each with an image — at 16
    workers with a 5s per-request timeout, a "export everything" run on
    ~500+ products could take minutes, well past Render's request timeout,
    which silently killed the whole export (no PDF, no error shown). Bounding
    total wall-clock time and skipping whatever images are still in flight
    once the budget runs out keeps the export reliable regardless of catalog
    size, at the cost of some products rendering without an image.
    """
    import httpx

    results: dict = {}
    if not urls:
        return results

    def _fetch(url: str):
        try:
            resp = httpx.get(url, timeout=3, follow_redirects=True, headers=_IMAGE_FETCH_HEADERS)
            if resp.status_code == 200:
                return url, _decoded_image_bytes(resp.content)
        except Exception:
            pass
        return url, None

    executor = ThreadPoolExecutor(max_workers=32)
    try:
        futures = {executor.submit(_fetch, url) for url in urls}
        done, _pending = wait(futures, timeout=overall_timeout)
        for f in done:
            try:
                url, content = f.result()
                if content:
                    results[url] = content
            except Exception:
                pass
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    return results


def _load_pdf_image(imagen_url: str, width, height, image_cache: Optional[dict] = None):
    """Load a product image for ReportLab. Supports base64 data URLs directly,
    and http(s) URLs via `image_cache` (see `_prefetch_images`)."""
    import base64, io as _io
    try:
        from reportlab.platypus import Image as RLImage
        if not imagen_url:
            return None
        if imagen_url.startswith("data:image"):
            data_part = imagen_url.split(",", 1)[1]
            img_bytes = base64.b64decode(data_part)
            return RLImage(_io.BytesIO(img_bytes), width=width, height=height)
        elif imagen_url.startswith("http"):
            img_bytes = (image_cache or {}).get(imagen_url)
            if img_bytes:
                return RLImage(_io.BytesIO(img_bytes), width=width, height=height)
    except Exception:
        pass
    return None


def _build_pdf_catalog(products: list, titulo: str, incluir_precios: bool) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    # Color palette — matches the Kairos brand colors used across the app
    # (catalog page header/buttons, price-list PDF): brown + gold, not the
    # previous generic navy/pink scheme.
    PRIMARY = HexColor("#4A3728")
    ACCENT = HexColor("#C9A040")
    LIGHT_GRAY = HexColor("#f5f5f5")
    MID_GRAY = HexColor("#888888")
    DARK_GRAY = HexColor("#333333")

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CatalogTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=28,
        textColor=PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=0.3 * cm,
    )

    subtitle_style = ParagraphStyle(
        "CatalogSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        textColor=MID_GRAY,
        alignment=TA_CENTER,
        spaceAfter=0.5 * cm,
    )

    section_header_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=white,
        alignment=TA_CENTER,
        spaceAfter=0,
    )

    product_name_style = ParagraphStyle(
        "ProductName",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=DARK_GRAY,
        spaceAfter=0.15 * cm,
    )

    product_desc_style = ParagraphStyle(
        "ProductDesc",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=MID_GRAY,
        spaceAfter=0.2 * cm,
        leading=11,
    )

    price_style = ParagraphStyle(
        "Price",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=ACCENT,
        spaceAfter=0.1 * cm,
    )

    price_label_style = ParagraphStyle(
        "PriceLabel",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        textColor=MID_GRAY,
    )

    sku_style = ParagraphStyle(
        "SKU",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=7,
        textColor=MID_GRAY,
    )

    story = []

    # Header
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(_pdf_text(titulo), title_style))
    story.append(Paragraph(
        f"Catálogo generado el {datetime.now().strftime('%d/%m/%Y')} · {len(products)} productos",
        subtitle_style,
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=0.5 * cm))

    if not products:
        story.append(Paragraph("No se encontraron productos.", styles["Normal"]))
        doc.build(story)
        return buffer.getvalue()

    image_urls = {p.get("imagen_url") for p in products if (p.get("imagen_url") or "").startswith("http")}
    image_cache = _prefetch_images(image_urls)

    # Group by category
    categories: dict = {}
    for p in products:
        cat = p.get("categoria") or "Sin categoría"
        categories.setdefault(cat, []).append(p)

    for cat_name, cat_products in categories.items():
        # Category header row
        cat_header_data = [[Paragraph(_pdf_text(cat_name.upper()), section_header_style)]]
        cat_table = Table(cat_header_data, colWidths=[doc.width])
        cat_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(cat_table)
        story.append(Spacer(1, 0.3 * cm))

        # Products grid — 2 columns
        col_width = (doc.width - 0.5 * cm) / 2
        grid_rows = []

        for i in range(0, len(cat_products), 2):
            row_cells = []
            for j in range(2):
                idx = i + j
                if idx >= len(cat_products):
                    row_cells.append("")
                    continue

                p = cat_products[idx]
                cell_content = []

                img_url = p.get("imagen_url", "")
                rl_img = _load_pdf_image(img_url, 3*cm, 3*cm, image_cache)
                if rl_img:
                    cell_content.append(rl_img)
                    cell_content.append(Spacer(1, 0.2 * cm))

                name_text = p.get("nombre", "Producto sin nombre")
                cell_content.append(Paragraph(_pdf_text(name_text), product_name_style))

                desc = p.get("descripcion") or ""
                if desc:
                    short_desc = desc[:200] + ("..." if len(desc) > 200 else "")
                    cell_content.append(Paragraph(_pdf_text(short_desc), product_desc_style))

                sku = p.get("sku")
                if sku:
                    cell_content.append(Paragraph(f"SKU: {_pdf_text(sku)}", sku_style))

                if incluir_precios:
                    def _fmt_price(val):
                        try:
                            return f"$ {float(val):,.0f}"
                        except (TypeError, ValueError):
                            return None

                    precio_min = p.get("precio_minorista")
                    precio_may = p.get("precio_mayorista")
                    precio_promo = p.get("precio_promo")

                    promo_str = _fmt_price(precio_promo)
                    min_str = _fmt_price(precio_min)
                    may_str = _fmt_price(precio_may)

                    if promo_str:
                        cell_content.append(Paragraph(promo_str, price_style))
                        cell_content.append(Paragraph("Precio promocional", price_label_style))
                    elif min_str:
                        cell_content.append(Paragraph(min_str, price_style))
                        cell_content.append(Paragraph("Precio minorista", price_label_style))

                    if may_str and precio_may != precio_min:
                        may_style = ParagraphStyle(
                            "MayPrice",
                            parent=styles["Normal"],
                            fontName="Helvetica-Bold",
                            fontSize=10,
                            textColor=PRIMARY,
                        )
                        cell_content.append(Paragraph(may_str, may_style))
                        cell_content.append(Paragraph("Precio mayorista", price_label_style))

                stock = p.get("stock")
                if stock is not None:
                    try:
                        stock_int = int(stock)
                        stock_color = HexColor("#c0392b") if stock_int <= 5 else HexColor("#27ae60")
                        stock_text = f"Stock: {stock_int} unidades" if stock_int > 0 else "Sin stock"
                        stock_style = ParagraphStyle(
                            "Stock",
                            parent=styles["Normal"],
                            fontName="Helvetica",
                            fontSize=7,
                            textColor=stock_color,
                        )
                        cell_content.append(Spacer(1, 0.1 * cm))
                        cell_content.append(Paragraph(stock_text, stock_style))
                    except (TypeError, ValueError):
                        pass

                row_cells.append(cell_content)

            grid_rows.append(row_cells)

        if grid_rows:
            product_table = Table(
                grid_rows,
                colWidths=[col_width, col_width],
                hAlign="LEFT",
            )
            product_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT_GRAY, white]),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e0e0e0")),
                ("ROUNDEDCORNERS", [4, 4, 4, 4]),
            ]))
            story.append(product_table)

        story.append(Spacer(1, 0.8 * cm))

    # Footer note
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        textColor=MID_GRAY,
        alignment=TA_CENTER,
    )
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#e0e0e0"), spaceBefore=0.3 * cm))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph("Precios expresados en pesos argentinos (ARS) · Sujetos a cambio sin previo aviso", footer_style))

    doc.build(story)
    return buffer.getvalue()


def _build_price_list_pdf(products: list, lead: dict, es_mayorista: bool) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, white
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)

    PRIMARY = HexColor("#4A3728")
    ACCENT = HexColor("#C9A040")
    LIGHT = HexColor("#f9f5ef")
    GRAY = HexColor("#888888")

    styles = getSampleStyleSheet()
    empresa = lead.get("empresa", "Cliente")
    tier_label = "Mayorista" if es_mayorista else "Minorista"

    title_style = ParagraphStyle("PLT", fontName="Helvetica-Bold", fontSize=22, textColor=PRIMARY, alignment=TA_CENTER)
    sub_style = ParagraphStyle("PLS", fontName="Helvetica", fontSize=12, textColor=GRAY, alignment=TA_CENTER)
    emp_style = ParagraphStyle("PLE", fontName="Helvetica-Bold", fontSize=16, textColor=ACCENT, alignment=TA_CENTER)
    col_header_style = ParagraphStyle("PLCH", fontName="Helvetica-Bold", fontSize=9, textColor=white)
    normal = ParagraphStyle("PLN", fontName="Helvetica", fontSize=10, textColor=HexColor("#333333"))
    price_style = ParagraphStyle("PLP", fontName="Helvetica-Bold", fontSize=10, textColor=ACCENT, alignment=TA_RIGHT)
    footer_style = ParagraphStyle("PLF", fontName="Helvetica-Oblique", fontSize=8, textColor=GRAY, alignment=TA_CENTER)

    def fmt(n):
        try:
            return f"$ {float(n):,.0f}".replace(",", ".")
        except Exception:
            return "—"

    story = []
    story.append(Paragraph("LISTA DE PRECIOS", title_style))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(_pdf_text(empresa), emp_style))
    story.append(Paragraph(f"Precio {tier_label} · {datetime.now().strftime('%d/%m/%Y')}", sub_style))
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT))
    story.append(Spacer(1, 0.5 * cm))

    by_cat: dict = {}
    for p in products:
        cat = (p.get("categoria") or "Otros").replace("-", " ").title()
        by_cat.setdefault(cat, []).append(p)

    col_widths = [doc.width * 0.65, doc.width * 0.35]

    for cat_name in sorted(by_cat):
        cat_products = by_cat[cat_name]
        header_table = Table(
            [[Paragraph(_pdf_text(cat_name.upper()), col_header_style), ""]],
            colWidths=col_widths,
        )
        header_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("SPAN", (0, 0), (-1, 0)),
        ]))
        story.append(header_table)

        rows = []
        for p in cat_products:
            if es_mayorista and p.get("precio_mayorista"):
                price_val = p["precio_mayorista"]
            elif p.get("precio_minorista"):
                price_val = p["precio_minorista"]
            else:
                price_val = None
            promo = p.get("precio_promo")
            price_text = fmt(promo) + " ✦" if promo else (fmt(price_val) if price_val is not None else "Consultar")
            rows.append([Paragraph(_pdf_text(p.get("nombre", "—")), normal), Paragraph(price_text, price_style)])

        if rows:
            prod_table = Table(rows, colWidths=col_widths)
            prod_table.setStyle(TableStyle([
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT, white]),
                ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#e0d8cc")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(prod_table)
        story.append(Spacer(1, 0.4 * cm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#e0d8cc")))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        f"Lista de precios {tier_label} — Precios en ARS — Sujetos a cambio sin previo aviso",
        footer_style,
    ))

    doc.build(story)
    return buffer.getvalue()


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@router.get("/categories")
def get_categories(current_org: OrgContext = Depends(get_current_org)):
    products = current_org.db.select("products", filters={"activo": "eq.true"}, select_cols="categoria")
    cats = list({p.get("categoria") for p in products if p.get("categoria")})
    cats.sort()
    return {"categories": cats}


@router.get("/search-image")
def search_product_image(
    sku: Optional[str] = None,
    nombre: Optional[str] = None,
    marca: Optional[str] = None,
    current_org: OrgContext = Depends(get_current_org),
):
    """Searches the web for candidate product images by SKU/name/brand, so
    a product missing a photo can be filled in without leaving the catalog
    editor. Free-text only: results aren't persisted, the caller picks one
    and saves it as `imagen_url` via the normal update endpoint."""
    query = " ".join(p.strip() for p in [marca, nombre, sku] if p and p.strip())
    if not query:
        raise HTTPException(status_code=400, detail="Indicá al menos sku, nombre o marca para buscar")

    results = ddg_image_search(query, max_results=12)
    return {"query": query, "results": results}


@router.get("")
def list_products(
    categoria: Optional[str] = None,
    activo: Optional[bool] = None,
    destacado: Optional[bool] = None,
    q: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    current_org: OrgContext = Depends(get_current_org),
):
    params: dict = {
        "select": "*",
        "order": "orden.asc.nullslast,nombre.asc",
        "limit": per_page,
        "offset": (page - 1) * per_page,
    }

    if categoria:
        params["categoria"] = f"ilike.%{categoria}%"
    if activo is not None:
        params["activo"] = f"eq.{str(activo).lower()}"
    if destacado is not None:
        params["destacado"] = f"eq.{str(destacado).lower()}"
    if q:
        params["nombre"] = f"ilike.%{q}%"

    products = current_org.db.raw_select("products", params)
    total = current_org.db.count("products")
    import math
    pages = max(1, math.ceil(total / per_page))
    return {"items": products, "total": total, "page": page, "pages": pages}


@router.post("")
def create_product(body: ProductCreate, current_org: OrgContext = Depends(get_current_org)):
    now = datetime.utcnow().isoformat()
    data = body.model_dump()
    data["created_at"] = now
    data["updated_at"] = now
    product = current_org.db.insert("products", data)
    return product


@router.put("/{product_id}")
@router.patch("/{product_id}")
def update_product(product_id: str, body: ProductUpdate, current_org: OrgContext = Depends(get_current_org)):
    existing = current_org.db.select("products", filters={"id": f"eq.{product_id}"}, limit=1)
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    prev = existing[0]
    price_changed = (
        ("precio_minorista" in update_data and update_data["precio_minorista"] != prev.get("precio_minorista")) or
        ("precio_mayorista" in update_data and update_data["precio_mayorista"] != prev.get("precio_mayorista"))
    )
    if price_changed:
        try:
            current_org.db.insert("product_price_history", {
                "product_id": product_id,
                "precio_minorista": update_data.get("precio_minorista", prev.get("precio_minorista")),
                "precio_mayorista": update_data.get("precio_mayorista", prev.get("precio_mayorista")),
                "changed_at": datetime.utcnow().isoformat(),
            })
        except Exception:
            pass

    update_data["updated_at"] = datetime.utcnow().isoformat()
    updated = current_org.db.update("products", product_id, update_data)
    return updated


@router.get("/{product_id}/price-history")
def get_price_history(product_id: str, limit: int = 10, current_org: OrgContext = Depends(get_current_org)):
    history = current_org.db.raw_select("product_price_history", {
        "select": "*",
        "product_id": f"eq.{product_id}",
        "order": "changed_at.desc",
        "limit": limit,
    })
    return {"history": history}


@router.delete("/{product_id}")
def delete_product(product_id: str, current_org: OrgContext = Depends(get_current_org)):
    products = current_org.db.select("products", filters={"id": f"eq.{product_id}"}, limit=1)
    if not products:
        raise HTTPException(status_code=404, detail="Product not found")

    current_org.db.update("products", product_id, {
        "activo": False,
        "updated_at": datetime.utcnow().isoformat(),
    })
    return {"message": "Product deactivated", "id": product_id}


@router.get("/low-stock")
def get_low_stock(threshold: int = 5, current_org: OrgContext = Depends(get_current_org)):
    products = current_org.db.select("products", filters={"activo": "eq.true"}, limit=5000)
    low = []
    for p in products:
        stock_val = p.get("stock")
        if stock_val is not None:
            try:
                if int(stock_val) <= threshold:
                    low.append(p)
            except (TypeError, ValueError):
                pass
    low.sort(key=lambda p: int(p.get("stock") or 0))
    return {"items": low, "total": len(low), "threshold": threshold}


@router.get("/price-list/{lead_id}")
def get_price_list(lead_id: str, current_org: OrgContext = Depends(get_current_org)):
    leads = current_org.db.select("leads", filters={"id": f"eq.{lead_id}"}, limit=1)
    if not leads:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = leads[0]

    products = current_org.db.select(
        "products",
        filters={"activo": "eq.true"},
        order="categoria.asc,nombre.asc",
        limit=5000,
    )
    if not products:
        raise HTTPException(status_code=404, detail="No products found")

    es_mayorista = lead.get("tipo_cliente") == "mayorista" or lead.get("estado") == "cliente"
    pdf_bytes = _build_price_list_pdf(products, lead, es_mayorista)
    empresa_slug = (lead.get("empresa") or "cliente").lower().replace(" ", "_")[:30]
    filename = f"lista_precios_{empresa_slug}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export-catalog")
def export_catalog_get(
    title: str = Query(default="Catálogo de Productos"),
    product_ids: Optional[List[str]] = Query(default=None),
    incluir_precios: bool = Query(default=True),
    current_org: OrgContext = Depends(get_current_org),
):
    if product_ids:
        ids_str = ",".join(product_ids)
        products = current_org.db.raw_select("products", {
            "select": "*",
            "id": f"in.({ids_str})",
            "activo": "eq.true",
        })
    else:
        products = current_org.db.select_all(
            "products",
            filters={"activo": "eq.true"},
        )
        products.sort(key=lambda p: (p.get("orden") is None, p.get("orden") or 0, p.get("nombre") or ""))

    if not products:
        raise HTTPException(status_code=404, detail="No products found")

    pdf_bytes = _build_pdf_catalog(products, title, incluir_precios)
    filename = f"catalogo_kairos_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/export-catalog")
def export_catalog(body: CatalogExportRequest, current_org: OrgContext = Depends(get_current_org)):
    if body.product_ids:
        ids_str = ",".join(body.product_ids)
        products = current_org.db.raw_select("products", {
            "select": "*",
            "id": f"in.({ids_str})",
            "activo": "eq.true",
        })
    else:
        products = current_org.db.select_all(
            "products",
            filters={"activo": "eq.true"},
        )
        products.sort(key=lambda p: (p.get("orden") is None, p.get("orden") or 0, p.get("nombre") or ""))

    if not products:
        raise HTTPException(status_code=404, detail="No products found")

    pdf_bytes = _build_pdf_catalog(products, body.titulo, body.incluir_precios)
    filename = f"catalogo_kairos_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    # Save export record
    current_org.db.insert("catalog_exports", {
        "nombre": body.titulo,
        "tipo": "pdf",
        "productos": [p.get("id") for p in products],
        "created_at": datetime.utcnow().isoformat(),
    })

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ─────────────────────────────────────────────
# KAIROSDIS.COM.AR PRODUCT SCRAPER
# Uses the site's internal Empretienda JSON API (/v4/product/category)
# which returns 12 products per page with full price + image data.
# ─────────────────────────────────────────────

_KAIROSDIS_BASE = "https://www.kairosdis.com.ar"
_KD_CDN = "https://d22fxaf9t8d39k.cloudfront.net/"

# Correct root-category URLs (verified from homepage JS — used if dynamic parse fails)
_KAIROSDIS_FALLBACK_CATEGORIES = [
    "/sahumerios", "/kits", "/velas", "/promos",
    "/hornillos-y-sahumadores", "/cascadas-de-humo", "/lamparas-de-sal",
    "/fuentes-de-agua", "/productos-aromaticos", "/portasahumerios",
    "/home-y-deco", "/defumacion", "/imagenes-gigantes-de-resina",
    "/tarot-libros", "/linea-santoral", "/yoga-y-relajacion",
    "/religion-y-ofrenda", "/bijou-llaveros", "/runas-pendulos-radiestesia",
    "/dijes", "/fluidos-esotericos", "/linea-vrinda", "/humificadores",
]

_KD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}

_kairosdis_job: dict = {
    "status": "idle", "progress": 0, "total": 0,
    "new": 0, "updated": 0, "errors": [],
}


def _kd_discover_categories() -> list:
    """
    Parse all root categories from the JSON blobs embedded in the homepage.
    Each category is serialised as {idCategorias:…, c_nombre:…, c_link_full:…, c_padre:null, …}.
    We extract those with c_padre == null (root categories).
    """
    import httpx, json as _json
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as c:
            html = c.get(_KAIROSDIS_BASE, headers=_KD_HEADERS).text

        # Every category object contains "c_nombre" — extract all JSON objects that do
        blobs = re.findall(r'\{[^{}]*"c_nombre"[^{}]*\}', html)
        paths = []
        for blob in blobs:
            try:
                obj = _json.loads(blob.replace(r'\/', '/'))
                if obj.get("c_padre") is None and obj.get("c_link_full"):
                    paths.append(obj["c_link_full"])
            except Exception:
                pass
        return paths
    except Exception:
        return []


def _kd_scrape_category(cat_path: str) -> tuple:
    """
    Fetch ALL products for a category via the /v4/product/category JSON API.
    Returns (category_name, [raw_product_dicts]).
    Each call creates its own httpx session to get a fresh CSRF token.
    """
    import httpx
    cat_name = cat_path.lstrip("/").split("/")[0]
    products_raw = []

    with httpx.Client(timeout=20, follow_redirects=True) as client:
        # Step 1: load the category page to obtain session cookie + CSRF + ids array
        time.sleep(0.3)
        resp = client.get(_KAIROSDIS_BASE + cat_path, headers=_KD_HEADERS)
        if resp.status_code != 200:
            return cat_name, []

        html = resp.text
        csrf_m = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
        ids_m = re.search(r'var ids = \[([^\]]+)\]', html)
        if not csrf_m or not ids_m:
            return cat_name, []

        csrf_token = csrf_m.group(1)
        ids = [x.strip() for x in ids_m.group(1).split(",")]

        api_headers = {
            **_KD_HEADERS,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRF-TOKEN": csrf_token,
            "Referer": _KAIROSDIS_BASE + cat_path,
        }

        # Step 2: paginate — 12 items per page, stop when < 12 returned
        for page in range(500):  # cap: 500 pages × 12 = 6 000 products max
            time.sleep(0.25)
            params = [("filter_page", page), ("filter_order", "2")]
            for cat_id in ids:
                params.append(("filter_categories[]", cat_id))

            try:
                api_resp = client.get(
                    _KAIROSDIS_BASE + "/v4/product/category",
                    params=params,
                    headers=api_headers,
                )
                if api_resp.status_code != 200:
                    break
                data = api_resp.json().get("data", [])
            except Exception:
                break

            if not data:
                break
            products_raw.extend(data)
            if len(data) < 12:
                break

    return cat_name, products_raw


def _kd_map_product(raw: dict, category: str) -> dict:
    """Map an Empretienda API product dict to our products table schema."""
    images = [
        _KD_CDN + img["i_link"]
        for img in raw.get("imagenes", [])
        if img.get("i_link")
    ]

    price = raw.get("p_precio") or None
    mayorista = raw.get("p_precio_mayorista") or None
    if mayorista == 0:
        mayorista = None
    promo = raw.get("p_precio_oferta") or None
    if promo == 0:
        promo = None

    desc = (raw.get("p_descripcion") or "").strip() or None

    # The source's stock entry marks "s_ilimitado" (unlimited/untracked) for
    # most products, with a meaningless s_cantidad of 0 in that case — that's
    # not the same as confirmed-zero stock. Use the real tracked quantity
    # when there is one; otherwise default to a flat 100 so untracked/
    # unlimited products show as available instead of "Sin stock".
    stock_entries = raw.get("stock") or []
    stock = 100
    if stock_entries and not stock_entries[0].get("s_ilimitado"):
        real_cantidad = stock_entries[0].get("s_cantidad")
        if real_cantidad:
            stock = real_cantidad

    return {
        "nombre": raw["p_nombre"],
        "sku": str(raw["idProductos"]),
        "descripcion": desc,
        "categoria": category,
        "precio_minorista": price,
        "precio_mayorista": mayorista,
        "precio_promo": promo,
        "imagen_url": images[0] if images else None,
        "imagenes_extra": images[1:] if len(images) > 1 else None,
        "stock": stock,
        "activo": not bool(raw.get("p_desactivado", 0)),
        "destacado": bool(raw.get("p_destacado", 0)),
    }


def _run_kairosdis_scraper(org_id: str) -> None:
    global _kairosdis_job
    scoped_db = ScopedSupabaseClient(db, org_id)
    _kairosdis_job = {
        "status": "Iniciando...", "progress": 0, "total": 0,
        "new": 0, "updated": 0, "errors": [],
    }

    try:
        # Phase 1: discover category pages
        _kairosdis_job["status"] = "Descubriendo categorías..."
        cat_paths = _kd_discover_categories()
        if len(cat_paths) < 3:
            cat_paths = _KAIROSDIS_FALLBACK_CATEGORIES

        _kairosdis_job["status"] = f"Cargando {len(cat_paths)} categorías via API..."

        # Phase 2: fetch all products from every category in parallel
        all_raw: list = []
        seen_ids: set = set()

        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = {ex.submit(_kd_scrape_category, p): p for p in cat_paths}
            done = 0
            for f in as_completed(futures):
                done += 1
                # First half of progress bar covers the API crawl phase
                _kairosdis_job["progress"] = int(done / len(cat_paths) * 50)
                try:
                    cat_name, products_raw = f.result()
                    for p in products_raw:
                        pid = str(p.get("idProductos", ""))
                        if pid and pid not in seen_ids:
                            seen_ids.add(pid)
                            p["_cat"] = cat_name
                            all_raw.append(p)
                except Exception as e:
                    _kairosdis_job["errors"].append(str(e)[:120])

        _kairosdis_job["total"] = len(all_raw)
        _kairosdis_job["status"] = f"Guardando {len(all_raw)} productos..."

        # Phase 3: upsert into products table
        existing = scoped_db.select("products", select_cols="id,sku")
        existing_skus: dict = {p["sku"]: p["id"] for p in existing if p.get("sku")}
        now = datetime.utcnow().isoformat()

        for i, raw in enumerate(all_raw):
            _kairosdis_job["progress"] = 50 + int(i / max(len(all_raw), 1) * 50)
            try:
                data = _kd_map_product(raw, raw.pop("_cat", "otros"))
                sku = data.get("sku")
                if sku and sku in existing_skus:
                    data["updated_at"] = now
                    scoped_db.update("products", existing_skus[sku], data)
                    _kairosdis_job["updated"] += 1
                else:
                    data["created_at"] = now
                    data["updated_at"] = now
                    inserted = scoped_db.insert("products", data)
                    _kairosdis_job["new"] += 1
                    if sku and isinstance(inserted, dict) and inserted.get("id"):
                        existing_skus[sku] = inserted["id"]
            except Exception as e:
                _kairosdis_job["errors"].append(str(e)[:120])

        _kairosdis_job["status"] = "completed"
        _kairosdis_job["progress"] = 100

    except Exception as e:
        _kairosdis_job["status"] = "error"
        _kairosdis_job["errors"].append(str(e)[:200])


@router.post("/scrape-kairosdis")
def start_kairosdis_scraper(background_tasks: BackgroundTasks, current_org: OrgContext = Depends(get_current_org)):
    if _kairosdis_job.get("status") not in ("idle", "completed", "error"):
        raise HTTPException(status_code=409, detail="Scraper ya en ejecución")
    org_id = current_org.organization_id
    background_tasks.add_task(_run_kairosdis_scraper, org_id)
    return {"status": "started", "message": "Importando desde kairosdis.com.ar en segundo plano"}


@router.get("/scrape-kairosdis/status")
def kairosdis_scraper_status(current_org: OrgContext = Depends(get_current_org)):
    return _kairosdis_job


# ─────────────────────────────────────────────
# GOOGLE SHEETS SYNC
# ─────────────────────────────────────────────

SHEET_COLUMNS = ["id", "sku", "nombre", "categoria", "precio_minorista",
                 "precio_mayorista", "precio_promo", "cantidad_mayorista", "stock", "activo"]

_SHEET_ID_KEY = "google_sheet_id"
_sheet_id_store: dict = {"id": ""}


@router.get("/export-csv")
def export_products_csv(current_org: OrgContext = Depends(get_current_org)):
    """Export all products as CSV for import into Google Sheets."""
    import csv as _csv
    products = current_org.db.select_all("products", select_cols=",".join(SHEET_COLUMNS))
    output = io.StringIO()
    writer = _csv.writer(output)
    writer.writerow(["ID", "SKU", "Nombre", "Categoría", "Precio Minorista",
                     "Precio Mayorista", "Precio Promo", "Cant. Mayorista", "Stock", "Activo"])
    for p in products:
        writer.writerow([
            p.get("id", ""),
            p.get("sku", ""),
            p.get("nombre", ""),
            (p.get("categoria") or "").replace("-", " ").title(),
            p.get("precio_minorista", ""),
            p.get("precio_mayorista", ""),
            p.get("precio_promo", ""),
            p.get("cantidad_mayorista", 6),
            p.get("stock", ""),
            "Sí" if p.get("activo") is not False else "No",
        ])
    csv_bytes = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=kairos_productos.csv"},
    )


class SheetSyncRequest(BaseModel):
    sheet_id: str


@router.post("/sync-from-sheet")
def sync_from_google_sheet(body: SheetSyncRequest, current_org: OrgContext = Depends(get_current_org)):
    """
    Read a Google Sheet (must be shared as 'Anyone with the link can view')
    and update prices, stock, and activo status in the CRM for matching SKUs.

    The sheet must have columns: ID, SKU, Nombre, Precio Minorista,
    Precio Mayorista, Precio Promo, Stock, Activo
    """
    import csv as _csv
    import httpx as _httpx

    sheet_id = body.sheet_id.strip()
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&id={sheet_id}"

    try:
        resp = _httpx.get(csv_url, follow_redirects=True, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo leer la hoja: {exc}")

    content = resp.text
    reader = _csv.DictReader(io.StringIO(content))

    updated = 0
    skipped = 0
    errors = []

    for row in reader:
        product_id = (row.get("ID") or "").strip()
        if not product_id:
            skipped += 1
            continue

        update_data: dict = {}

        for src_col, db_col in [
            ("Precio Minorista", "precio_minorista"),
            ("Precio Mayorista", "precio_mayorista"),
            ("Precio Promo", "precio_promo"),
        ]:
            val = (row.get(src_col) or "").strip()
            if val:
                try:
                    update_data[db_col] = float(val.replace(",", "."))
                except ValueError:
                    pass

        cant_may = (row.get("Cant. Mayorista") or "").strip()
        if cant_may:
            try:
                update_data["cantidad_mayorista"] = int(float(cant_may))
            except ValueError:
                pass

        stock_str = (row.get("Stock") or "").strip()
        if stock_str:
            try:
                update_data["stock"] = int(float(stock_str))
            except ValueError:
                pass

        activo_str = (row.get("Activo") or "").strip().lower()
        if activo_str in ("sí", "si", "yes", "true", "1"):
            update_data["activo"] = True
        elif activo_str in ("no", "false", "0"):
            update_data["activo"] = False

        if not update_data:
            skipped += 1
            continue

        update_data["updated_at"] = datetime.utcnow().isoformat()
        try:
            current_org.db.update("products", product_id, update_data)
            updated += 1
        except Exception as exc:
            errors.append(f"{product_id}: {exc}")

    return {
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:10],
    }

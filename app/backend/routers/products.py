import io
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.supabase_client import db

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

def _load_pdf_image(imagen_url: str, width, height):
    """Load a product image for ReportLab. Supports base64 data URLs and http(s) URLs."""
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
            import httpx
            resp = httpx.get(imagen_url, timeout=5, follow_redirects=True)
            if resp.status_code == 200:
                return RLImage(_io.BytesIO(resp.content), width=width, height=height)
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

    # Color palette
    PRIMARY = HexColor("#1a1a2e")
    ACCENT = HexColor("#e94560")
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
    story.append(Paragraph(titulo, title_style))
    story.append(Paragraph(
        f"Catálogo generado el {datetime.now().strftime('%d/%m/%Y')} · {len(products)} productos",
        subtitle_style,
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=0.5 * cm))

    if not products:
        story.append(Paragraph("No se encontraron productos.", styles["Normal"]))
        doc.build(story)
        return buffer.getvalue()

    # Group by category
    categories: dict = {}
    for p in products:
        cat = p.get("categoria") or "Sin categoría"
        categories.setdefault(cat, []).append(p)

    for cat_name, cat_products in categories.items():
        # Category header row
        cat_header_data = [[Paragraph(cat_name.upper(), section_header_style)]]
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
                rl_img = _load_pdf_image(img_url, 3*cm, 3*cm)
                if rl_img:
                    cell_content.append(rl_img)
                    cell_content.append(Spacer(1, 0.2 * cm))

                name_text = p.get("nombre", "Producto sin nombre")
                cell_content.append(Paragraph(name_text, product_name_style))

                desc = p.get("descripcion") or ""
                if desc:
                    short_desc = desc[:200] + ("..." if len(desc) > 200 else "")
                    cell_content.append(Paragraph(short_desc, product_desc_style))

                sku = p.get("sku")
                if sku:
                    cell_content.append(Paragraph(f"SKU: {sku}", sku_style))

                if incluir_precios:
                    precio_min = p.get("precio_minorista")
                    precio_may = p.get("precio_mayorista")
                    precio_promo = p.get("precio_promo")

                    if precio_promo:
                        cell_content.append(Paragraph(f"$ {precio_promo:,.0f}", price_style))
                        cell_content.append(Paragraph("Precio promocional", price_label_style))
                    elif precio_min:
                        cell_content.append(Paragraph(f"$ {precio_min:,.0f}", price_style))
                        cell_content.append(Paragraph("Precio minorista", price_label_style))

                    if precio_may and precio_may != precio_min:
                        may_style = ParagraphStyle(
                            "MayPrice",
                            parent=styles["Normal"],
                            fontName="Helvetica-Bold",
                            fontSize=10,
                            textColor=PRIMARY,
                        )
                        cell_content.append(Paragraph(f"$ {precio_may:,.0f}", may_style))
                        cell_content.append(Paragraph("Precio mayorista", price_label_style))

                stock = p.get("stock")
                if stock is not None:
                    stock_color = ACCENT if stock <= 5 else HexColor("#27ae60")
                    stock_text = f"Stock: {stock} unidades" if stock > 0 else "Sin stock"
                    stock_style = ParagraphStyle(
                        "Stock",
                        parent=styles["Normal"],
                        fontName="Helvetica",
                        fontSize=7,
                        textColor=stock_color,
                    )
                    cell_content.append(Spacer(1, 0.1 * cm))
                    cell_content.append(Paragraph(stock_text, stock_style))

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
                ("ROUNDEDCORNERS", [4]),
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


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@router.get("/categories")
def get_categories():
    products = db.select("products", filters={"activo": "eq.true"}, select_cols="categoria")
    cats = list({p.get("categoria") for p in products if p.get("categoria")})
    cats.sort()
    return {"categories": cats}


@router.get("")
def list_products(
    categoria: Optional[str] = None,
    activo: Optional[bool] = None,
    destacado: Optional[bool] = None,
    q: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
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

    products = db.raw_select("products", params)
    total = db.count("products")
    import math
    pages = max(1, math.ceil(total / per_page))
    return {"items": products, "total": total, "page": page, "pages": pages}


@router.post("")
def create_product(body: ProductCreate):
    now = datetime.utcnow().isoformat()
    data = body.model_dump()
    data["created_at"] = now
    data["updated_at"] = now
    product = db.insert("products", data)
    return product


@router.put("/{product_id}")
def update_product(product_id: str, body: ProductUpdate):
    products = db.select("products", filters={"id": f"eq.{product_id}"}, limit=1)
    if not products:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_data["updated_at"] = datetime.utcnow().isoformat()
    updated = db.update("products", product_id, update_data)
    return updated


@router.delete("/{product_id}")
def delete_product(product_id: str):
    products = db.select("products", filters={"id": f"eq.{product_id}"}, limit=1)
    if not products:
        raise HTTPException(status_code=404, detail="Product not found")

    db.update("products", product_id, {
        "activo": False,
        "updated_at": datetime.utcnow().isoformat(),
    })
    return {"message": "Product deactivated", "id": product_id}


@router.get("/export-catalog")
def export_catalog_get(
    title: str = Query(default="Catálogo de Productos"),
    product_ids: Optional[List[str]] = Query(default=None),
    incluir_precios: bool = Query(default=True),
):
    if product_ids:
        ids_str = ",".join(product_ids)
        products = db.raw_select("products", {
            "select": "*",
            "id": f"in.({ids_str})",
            "activo": "eq.true",
        })
    else:
        products = db.select(
            "products",
            filters={"activo": "eq.true"},
            order="orden.asc.nullslast,nombre.asc",
        )

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
def export_catalog(body: CatalogExportRequest):
    if body.product_ids:
        ids_str = ",".join(body.product_ids)
        products = db.raw_select("products", {
            "select": "*",
            "id": f"in.({ids_str})",
            "activo": "eq.true",
        })
    else:
        products = db.select(
            "products",
            filters={"activo": "eq.true"},
            order="orden.asc.nullslast,nombre.asc",
        )

    if not products:
        raise HTTPException(status_code=404, detail="No products found")

    pdf_bytes = _build_pdf_catalog(products, body.titulo, body.incluir_precios)
    filename = f"catalogo_kairos_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    # Save export record
    db.insert("catalog_exports", {
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

# Known main-category URLs — used as fallback if homepage nav parse fails
_KAIROSDIS_FALLBACK_CATEGORIES = [
    "/sahumerios", "/velas", "/dijes", "/kits-y-promociones",
    "/difusores-y-quemadores", "/fuentes-de-agua",
    "/decoracion", "/tarot-y-libros", "/imagenes-religiosas",
    "/fluidos-esotericos",
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

_KD_SKIP = {
    "/carrito", "/cart", "/cuenta", "/account", "/login", "/ingresa",
    "/checkout", "/buscar", "/search", "/contacto", "/newsletter",
    "/quienes-somos", "/sobre-nosotros", "/envios", "/terminos",
    "/privacidad", "/mapa-del-sitio",
}

_kairosdis_job: dict = {
    "status": "idle", "progress": 0, "total": 0,
    "new": 0, "updated": 0, "errors": [],
}


def _kd_discover_categories() -> list:
    """Fetch homepage and extract 1-segment category paths from nav links."""
    import httpx
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as c:
            resp = c.get(_KAIROSDIS_BASE, headers=_KD_HEADERS)
        links = set()
        for href in re.findall(r'href=["\']([^"\']+)["\']', resp.text):
            path = href.strip().rstrip("/")
            if (path.startswith("/") and path.count("/") == 1
                    and re.match(r'^/[a-zA-Z]', path)
                    and not re.search(r'\.\w+$', path)
                    and path not in _KD_SKIP):
                links.add(path)
        return list(links)
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
        "activo": not bool(raw.get("p_desactivado", 0)),
        "destacado": bool(raw.get("p_destacado", 0)),
    }


def _run_kairosdis_scraper() -> None:
    global _kairosdis_job
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
        existing = db.select("products", select_cols="id,sku")
        existing_skus: dict = {p["sku"]: p["id"] for p in existing if p.get("sku")}
        now = datetime.utcnow().isoformat()

        for i, raw in enumerate(all_raw):
            _kairosdis_job["progress"] = 50 + int(i / max(len(all_raw), 1) * 50)
            try:
                data = _kd_map_product(raw, raw.pop("_cat", "otros"))
                sku = data.get("sku")
                if sku and sku in existing_skus:
                    data["updated_at"] = now
                    db.update("products", existing_skus[sku], data)
                    _kairosdis_job["updated"] += 1
                else:
                    data["created_at"] = now
                    data["updated_at"] = now
                    inserted = db.insert("products", data)
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
def start_kairosdis_scraper(background_tasks: BackgroundTasks):
    if _kairosdis_job.get("status") not in ("idle", "completed", "error"):
        raise HTTPException(status_code=409, detail="Scraper ya en ejecución")
    background_tasks.add_task(_run_kairosdis_scraper)
    return {"status": "started", "message": "Importando desde kairosdis.com.ar en segundo plano"}


@router.get("/scrape-kairosdis/status")
def kairosdis_scraper_status():
    return _kairosdis_job

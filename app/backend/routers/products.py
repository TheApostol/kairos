import io
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
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

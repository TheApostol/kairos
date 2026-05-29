from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.backend.services.supabase_client import db

router = APIRouter(prefix="/orders", tags=["orders"])


# ─────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────

class OrderItemCreate(BaseModel):
    product_id: Optional[str] = None
    nombre: str
    cantidad: int
    precio_unit: float


class OrderCreate(BaseModel):
    lead_id: Optional[str] = None
    numero: Optional[str] = None
    estado: str = "pendiente"
    moneda: str = "ARS"
    descuento: float = 0.0
    notas: Optional[str] = None
    fecha_entrega: Optional[str] = None
    items: List[OrderItemCreate] = []


class OrderUpdate(BaseModel):
    estado: Optional[str] = None
    notas: Optional[str] = None
    fecha_entrega: Optional[str] = None
    descuento: Optional[float] = None


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _generate_order_number() -> str:
    now = datetime.utcnow()
    return f"ORD-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"


def _calculate_order_totals(items: list, descuento: float = 0.0) -> dict:
    subtotal = sum(float(item.get("subtotal", 0)) for item in items)
    total = max(0.0, subtotal - float(descuento))
    return {"subtotal": round(subtotal, 2), "total": round(total, 2)}


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@router.get("/stats")
def get_orders_stats():
    orders = db.select("orders", limit=10000)

    total_revenue = 0.0
    by_estado: dict = {}
    monthly_revenue: dict = {}

    for order in orders:
        estado = order.get("estado") or "desconocido"
        by_estado[estado] = by_estado.get(estado, 0) + 1

        total = order.get("total") or 0
        try:
            total = float(total)
        except (ValueError, TypeError):
            total = 0.0

        if order.get("estado") not in ("cancelado", "devuelto"):
            total_revenue += total

        fecha = order.get("fecha_pedido") or order.get("created_at", "")
        if fecha and len(fecha) >= 7:
            month_key = fecha[:7]  # YYYY-MM
            monthly_revenue[month_key] = round(
                monthly_revenue.get(month_key, 0.0) + total, 2
            )

    return {
        "total_orders": len(orders),
        "total_revenue": round(total_revenue, 2),
        "by_estado": by_estado,
        "monthly_revenue": dict(sorted(monthly_revenue.items())),
    }


@router.get("")
def list_orders(
    estado: Optional[str] = None,
    lead_id: Optional[str] = None,
    fecha_from: Optional[str] = None,
    fecha_to: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
):
    params: dict = {
        "select": "*",
        "order": "created_at.desc",
        "limit": per_page,
        "offset": (page - 1) * per_page,
    }

    if estado:
        params["estado"] = f"eq.{estado}"
    if lead_id:
        params["lead_id"] = f"eq.{lead_id}"
    if fecha_from:
        params["fecha_pedido"] = f"gte.{fecha_from}"
    if fecha_to:
        params["fecha_pedido"] = f"lte.{fecha_to}"

    orders = db.raw_select("orders", params)
    return {"data": orders, "page": page, "per_page": per_page, "count": len(orders)}


@router.post("")
def create_order(body: OrderCreate):
    numero = body.numero or _generate_order_number()
    now = datetime.utcnow().isoformat()

    # Calculate item subtotals
    items_data = []
    for item in body.items:
        subtotal = round(item.cantidad * item.precio_unit, 2)
        items_data.append({
            "product_id": item.product_id,
            "nombre": item.nombre,
            "cantidad": item.cantidad,
            "precio_unit": item.precio_unit,
            "subtotal": subtotal,
        })

    totals = _calculate_order_totals(items_data, body.descuento)

    order_data = {
        "lead_id": body.lead_id,
        "numero": numero,
        "estado": body.estado,
        "subtotal": totals["subtotal"],
        "descuento": body.descuento,
        "total": totals["total"],
        "moneda": body.moneda,
        "notas": body.notas,
        "fecha_pedido": now,
        "fecha_entrega": body.fecha_entrega,
        "created_at": now,
        "updated_at": now,
    }

    order = db.insert("orders", order_data)
    order_id = order.get("id")

    created_items = []
    for item in items_data:
        item["order_id"] = order_id
        created_item = db.insert("order_items", item)
        created_items.append(created_item)

    order["items"] = created_items
    return order


@router.get("/{order_id}")
def get_order(order_id: str):
    orders = db.select("orders", filters={"id": f"eq.{order_id}"}, limit=1)
    if not orders:
        raise HTTPException(status_code=404, detail="Order not found")

    order = orders[0]

    items = db.select("order_items", filters={"order_id": f"eq.{order_id}"})
    order["items"] = items

    lead = None
    if order.get("lead_id"):
        leads = db.select("leads", filters={"id": f"eq.{order['lead_id']}"}, limit=1)
        if leads:
            lead = {
                k: leads[0].get(k)
                for k in ["id", "empresa", "email", "telefono", "ciudad", "provincia"]
            }
    order["lead"] = lead

    return order


@router.put("/{order_id}")
def update_order(order_id: str, body: OrderUpdate):
    orders = db.select("orders", filters={"id": f"eq.{order_id}"}, limit=1)
    if not orders:
        raise HTTPException(status_code=404, detail="Order not found")

    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_data["updated_at"] = datetime.utcnow().isoformat()
    updated = db.update("orders", order_id, update_data)

    # Recalculate total if discount changed
    if "descuento" in update_data:
        items = db.select("order_items", filters={"order_id": f"eq.{order_id}"})
        totals = _calculate_order_totals(items, update_data["descuento"])
        db.update("orders", order_id, {
            "subtotal": totals["subtotal"],
            "total": totals["total"],
        })
        updated["subtotal"] = totals["subtotal"]
        updated["total"] = totals["total"]

    return updated


@router.post("/{order_id}/items")
def add_order_item(order_id: str, body: OrderItemCreate):
    orders = db.select("orders", filters={"id": f"eq.{order_id}"}, limit=1)
    if not orders:
        raise HTTPException(status_code=404, detail="Order not found")

    subtotal = round(body.cantidad * body.precio_unit, 2)
    item_data = {
        "order_id": order_id,
        "product_id": body.product_id,
        "nombre": body.nombre,
        "cantidad": body.cantidad,
        "precio_unit": body.precio_unit,
        "subtotal": subtotal,
    }
    new_item = db.insert("order_items", item_data)

    # Recalculate order totals
    all_items = db.select("order_items", filters={"order_id": f"eq.{order_id}"})
    order = orders[0]
    descuento = float(order.get("descuento") or 0)
    totals = _calculate_order_totals(all_items, descuento)
    db.update("orders", order_id, {
        "subtotal": totals["subtotal"],
        "total": totals["total"],
        "updated_at": datetime.utcnow().isoformat(),
    })

    return new_item


@router.delete("/{order_id}/items/{item_id}")
def delete_order_item(order_id: str, item_id: str):
    items = db.select(
        "order_items",
        filters={"id": f"eq.{item_id}", "order_id": f"eq.{order_id}"},
        limit=1,
    )
    if not items:
        raise HTTPException(status_code=404, detail="Order item not found")

    db.delete("order_items", item_id)

    orders = db.select("orders", filters={"id": f"eq.{order_id}"}, limit=1)
    if orders:
        remaining_items = db.select("order_items", filters={"order_id": f"eq.{order_id}"})
        order = orders[0]
        descuento = float(order.get("descuento") or 0)
        totals = _calculate_order_totals(remaining_items, descuento)
        db.update("orders", order_id, {
            "subtotal": totals["subtotal"],
            "total": totals["total"],
            "updated_at": datetime.utcnow().isoformat(),
        })

    return {"message": "Item deleted"}

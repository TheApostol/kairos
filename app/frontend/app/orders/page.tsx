'use client'

import { useEffect, useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { getOrders, getLeads, getProducts, createOrder } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Plus, Loader2, ShoppingCart, Package } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

interface Order {
  id: number
  numero: string
  estado: string
  total: number
  lead_id?: number
  empresa?: string
  created_at?: string
}

interface Lead {
  id: number
  empresa: string
}

interface Product {
  id: number
  nombre: string
  precio_mayorista?: number
  precio_minorista?: number
  stock?: number
}

const ESTADOS = ['borrador', 'confirmado', 'en_preparacion', 'despachado', 'entregado']
const ESTADO_LABELS: Record<string, string> = {
  borrador: 'Borrador',
  confirmado: 'Confirmado',
  en_preparacion: 'En Preparación',
  despachado: 'Despachado',
  entregado: 'Entregado',
}
const ESTADO_COLORS: Record<string, string> = {
  borrador: 'bg-slate-100 border-slate-200',
  confirmado: 'bg-blue-50 border-blue-100',
  en_preparacion: 'bg-amber-50 border-amber-100',
  despachado: 'bg-violet-50 border-violet-100',
  entregado: 'bg-emerald-50 border-emerald-100',
}

function formatCurrency(n: number) {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n)
}

function formatDate(dateStr?: string) {
  if (!dateStr) return ''
  try {
    return format(new Date(dateStr), "d MMM", { locale: es })
  } catch {
    return ''
  }
}

function OrdersContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [showDialog, setShowDialog] = useState(false)

  // New order form
  const [leads, setLeads] = useState<Lead[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [selectedLead, setSelectedLead] = useState<string>('')
  const [orderItems, setOrderItems] = useState<Array<{ product_id: string; cantidad: number }>>([
    { product_id: '', cantidad: 1 },
  ])
  const [creating, setCreating] = useState(false)

  const filterLeadId = searchParams.get('lead_id')

  useEffect(() => {
    const params: Record<string, string> = {}
    if (filterLeadId) params.lead_id = filterLeadId
    getOrders(params)
      .then((data) => setOrders(data.items ?? data ?? []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [filterLeadId])

  const openNewOrderDialog = async () => {
    setShowDialog(true)
    if (filterLeadId) setSelectedLead(filterLeadId)
    try {
      const [l, p] = await Promise.all([
        getLeads({ limit: 200 }),
        getProducts(),
      ])
      setLeads(l.items ?? l ?? [])
      setProducts(p.items ?? p ?? [])
    } catch {}
  }

  const handleCreateOrder = async () => {
    if (!selectedLead) return
    setCreating(true)
    try {
      const items = orderItems.filter((i) => i.product_id)
      await createOrder({
        lead_id: parseInt(selectedLead),
        estado: 'borrador',
        items: items.map((i) => ({
          product_id: parseInt(i.product_id),
          cantidad: i.cantidad,
        })),
      })
      const data = await getOrders(filterLeadId ? { lead_id: filterLeadId } : undefined)
      setOrders(data.items ?? data ?? [])
      setShowDialog(false)
      setSelectedLead('')
      setOrderItems([{ product_id: '', cantidad: 1 }])
    } catch {
    } finally {
      setCreating(false)
    }
  }

  const byStatus = ESTADOS.reduce<Record<string, Order[]>>((acc, e) => {
    acc[e] = orders.filter((o) => o.estado === e)
    return acc
  }, {})

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Órdenes</h1>
          <p className="text-slate-500 mt-1">{orders.length} órdenes en total</p>
        </div>
        <Button onClick={openNewOrderDialog} className="gap-2">
          <Plus className="w-4 h-4" />
          Nueva Orden
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
        </div>
      ) : (
        /* Kanban Board */
        <div className="flex gap-4 items-start overflow-x-auto pb-4 sm:grid sm:grid-cols-2 sm:overflow-visible lg:grid-cols-5 sm:pb-0">
          <style>{`.kanban-col { min-width: 240px; flex-shrink: 0; } @media (min-width: 640px) { .kanban-col { min-width: unset; flex-shrink: unset; } }`}</style>
          {ESTADOS.map((estado) => (
            <div key={estado} className={`kanban-col rounded-xl border-2 ${ESTADO_COLORS[estado]} p-3`}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-slate-700">{ESTADO_LABELS[estado]}</h3>
                <span className="text-xs font-bold text-slate-500 bg-white/60 px-2 py-0.5 rounded-full">
                  {byStatus[estado].length}
                </span>
              </div>
              <div className="space-y-2">
                {byStatus[estado].length === 0 ? (
                  <div className="text-center py-6 text-slate-400">
                    <Package className="w-6 h-6 mx-auto mb-1 opacity-40" />
                    <p className="text-xs">Sin órdenes</p>
                  </div>
                ) : (
                  byStatus[estado].map((order) => (
                    <Card
                      key={order.id}
                      className="cursor-pointer hover:shadow-md transition-shadow bg-white"
                      onClick={() => router.push(`/orders/${order.id}`)}
                    >
                      <CardContent className="p-3">
                        <div className="flex items-start justify-between">
                          <p className="text-xs font-mono text-slate-500">#{order.numero}</p>
                          <span className="text-xs text-slate-400">{formatDate(order.created_at)}</span>
                        </div>
                        <p className="text-sm font-semibold text-slate-900 mt-1 leading-tight">
                          {order.empresa || `Lead #${order.lead_id}`}
                        </p>
                        <p className="text-sm font-bold text-emerald-700 mt-2">
                          {formatCurrency(order.total)}
                        </p>
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* New Order Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Nueva Orden</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label>Cliente (Lead)</Label>
              <Select value={selectedLead} onValueChange={setSelectedLead}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar lead..." />
                </SelectTrigger>
                <SelectContent>
                  {leads.map((l) => (
                    <SelectItem key={l.id} value={String(l.id)}>{l.empresa}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Productos</Label>
              {orderItems.map((item, idx) => (
                <div key={idx} className="flex gap-2">
                  <Select
                    value={item.product_id}
                    onValueChange={(v) => {
                      const updated = [...orderItems]
                      updated[idx].product_id = v
                      setOrderItems(updated)
                    }}
                  >
                    <SelectTrigger className="flex-1">
                      <SelectValue placeholder="Producto..." />
                    </SelectTrigger>
                    <SelectContent>
                      {products.map((p) => (
                        <SelectItem key={p.id} value={String(p.id)}>
                          {p.nombre}
                          {p.precio_mayorista ? ` — ${formatCurrency(p.precio_mayorista)}` : ''}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input
                    type="number"
                    min={1}
                    value={item.cantidad}
                    onChange={(e) => {
                      const updated = [...orderItems]
                      updated[idx].cantidad = parseInt(e.target.value) || 1
                      setOrderItems(updated)
                    }}
                    className="w-20"
                  />
                  {orderItems.length > 1 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-red-500 hover:text-red-600"
                      onClick={() => setOrderItems(orderItems.filter((_, i) => i !== idx))}
                    >
                      ✕
                    </Button>
                  )}
                </div>
              ))}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setOrderItems([...orderItems, { product_id: '', cantidad: 1 }])}
              >
                + Agregar producto
              </Button>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)}>Cancelar</Button>
            <Button onClick={handleCreateOrder} disabled={!selectedLead || creating}>
              {creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Crear Orden
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default function OrdersPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 animate-spin text-slate-400" /></div>}>
      <OrdersContent />
    </Suspense>
  )
}

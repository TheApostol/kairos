'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { getOrder, updateOrder, getProducts } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ArrowLeft, Loader2, Trash2, Plus } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

interface OrderItem {
  id?: number
  product_id: number
  nombre?: string
  cantidad: number
  precio_unit: number
  subtotal?: number
}

interface Order {
  id: number
  numero: string
  estado: string
  lead_id?: number
  empresa?: string
  notas?: string
  descuento?: number
  created_at?: string
  updated_at?: string
  items?: OrderItem[]
}

interface Product {
  id: number
  nombre: string
  precio_mayorista?: number
}

const ESTADOS = ['borrador', 'confirmado', 'en_preparacion', 'despachado', 'entregado']
const ESTADO_LABELS: Record<string, string> = {
  borrador: 'Borrador',
  confirmado: 'Confirmado',
  en_preparacion: 'En Preparación',
  despachado: 'Despachado',
  entregado: 'Entregado',
}

function formatCurrency(n: number) {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n)
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '—'
  try {
    return format(new Date(dateStr), "d 'de' MMMM yyyy, HH:mm", { locale: es })
  } catch {
    return dateStr
  }
}

export default function OrderDetailPage() {
  const params = useParams()
  const router = useRouter()
  const id = params.id as string

  const [order, setOrder] = useState<Order | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [items, setItems] = useState<OrderItem[]>([])
  const [estado, setEstado] = useState('')
  const [notas, setNotas] = useState('')
  const [descuento, setDescuento] = useState(0)
  const [hasChanges, setHasChanges] = useState(false)

  useEffect(() => {
    Promise.all([getOrder(id), getProducts()])
      .then(([o, p]) => {
        setOrder(o)
        setItems(o.items ?? [])
        setEstado(o.estado)
        setNotas(o.notas ?? '')
        setDescuento(o.descuento ?? 0)
        setProducts(p.items ?? p ?? [])
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [id])

  const subtotal = items.reduce((sum, item) => sum + item.cantidad * item.precio_unit, 0)
  const total = Math.max(0, subtotal - descuento)

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await updateOrder(id, {
        estado,
        notas,
        descuento,
        items: items.map((i) => ({
          product_id: i.product_id,
          cantidad: i.cantidad,
          precio_unit: i.precio_unit,
        })),
      })
      setOrder(updated)
      setHasChanges(false)
    } catch {
    } finally {
      setSaving(false)
    }
  }

  const addItem = () => {
    if (products.length === 0) return
    const first = products[0]
    setItems([
      ...items,
      {
        product_id: first.id,
        nombre: first.nombre,
        cantidad: 1,
        precio_unit: first.precio_mayorista ?? 0,
      },
    ])
    setHasChanges(true)
  }

  const removeItem = (idx: number) => {
    setItems(items.filter((_, i) => i !== idx))
    setHasChanges(true)
  }

  const updateItem = (idx: number, field: keyof OrderItem, value: string | number) => {
    const updated = [...items]
    if (field === 'product_id') {
      const prod = products.find((p) => p.id === Number(value))
      updated[idx] = {
        ...updated[idx],
        product_id: Number(value),
        nombre: prod?.nombre,
        precio_unit: prod?.precio_mayorista ?? updated[idx].precio_unit,
      }
    } else {
      updated[idx] = { ...updated[idx], [field]: value }
    }
    setItems(updated)
    setHasChanges(true)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
      </div>
    )
  }

  if (!order) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500">Orden no encontrada</p>
        <Button variant="ghost" onClick={() => router.push('/orders')} className="mt-4">Volver</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push('/orders')}>
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900">Orden #{order.numero}</h1>
            <Badge variant="secondary" className="capitalize">{ESTADO_LABELS[order.estado] ?? order.estado}</Badge>
          </div>
          <p className="text-slate-500 mt-1">{order.empresa || `Lead #${order.lead_id}`}</p>
        </div>
        <Button onClick={handleSave} disabled={!hasChanges || saving}>
          {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
          Guardar
        </Button>
      </div>

      {/* Order Header Info */}
      <Card>
        <CardContent className="pt-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label>Estado</Label>
              <Select value={estado} onValueChange={(v) => { setEstado(v); setHasChanges(true) }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ESTADOS.map((e) => (
                    <SelectItem key={e} value={e}>{ESTADO_LABELS[e]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-slate-500">Creado</Label>
              <p className="text-sm mt-1">{formatDate(order.created_at)}</p>
            </div>
            <div>
              <Label className="text-slate-500">Actualizado</Label>
              <p className="text-sm mt-1">{formatDate(order.updated_at)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Items Table */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Productos</CardTitle>
            <Button variant="outline" size="sm" onClick={addItem}>
              <Plus className="w-4 h-4 mr-1" />
              Agregar
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {items.length === 0 ? (
            <div className="text-center py-8 text-slate-400">
              <p className="text-sm">Sin productos en esta orden</p>
              <Button variant="outline" size="sm" className="mt-3" onClick={addItem}>
                Agregar producto
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Producto</TableHead>
                  <TableHead className="w-28">Cantidad</TableHead>
                  <TableHead className="w-36">Precio Unit.</TableHead>
                  <TableHead className="w-36 text-right">Subtotal</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item, idx) => (
                  <TableRow key={idx}>
                    <TableCell>
                      <Select
                        value={String(item.product_id)}
                        onValueChange={(v) => updateItem(idx, 'product_id', v)}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {products.map((p) => (
                            <SelectItem key={p.id} value={String(p.id)}>{p.nombre}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={1}
                        value={item.cantidad}
                        onChange={(e) => updateItem(idx, 'cantidad', parseInt(e.target.value) || 1)}
                        className="w-24"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={0}
                        value={item.precio_unit}
                        onChange={(e) => updateItem(idx, 'precio_unit', parseFloat(e.target.value) || 0)}
                        className="w-32"
                      />
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {formatCurrency(item.cantidad * item.precio_unit)}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-red-400 hover:text-red-600"
                        onClick={() => removeItem(idx)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Totals + Notes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Notes */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Notas de la Orden</CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              value={notas}
              onChange={(e) => { setNotas(e.target.value); setHasChanges(true) }}
              placeholder="Instrucciones especiales, notas de entrega..."
              rows={4}
            />
          </CardContent>
        </Card>

        {/* Totals */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Totales</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">Subtotal</span>
              <span className="font-medium">{formatCurrency(subtotal)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-600">Descuento</span>
              <Input
                type="number"
                min={0}
                value={descuento}
                onChange={(e) => { setDescuento(parseFloat(e.target.value) || 0); setHasChanges(true) }}
                className="w-32 text-right"
              />
            </div>
            <div className="border-t pt-3 flex justify-between">
              <span className="font-semibold text-slate-900">Total</span>
              <span className="text-lg font-bold text-emerald-700">{formatCurrency(total)}</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

'use client'

import { useEffect, useState } from 'react'
import { getProducts, createProduct, updateProduct, getApiUrl } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
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
import { Switch } from '@/components/ui/switch'
import { Plus, Loader2, Package, Pencil, Star, FileDown } from 'lucide-react'

interface Product {
  id: number
  nombre: string
  descripcion?: string
  categoria?: string
  precio_minorista?: number
  precio_mayorista?: number
  stock?: number
  activo?: boolean
  destacado?: boolean
  imagen_url?: string
}

const CATEGORIAS = [
  'aceites esenciales', 'aceites portadores', 'hidrolatos', 'blends',
  'difusores', 'nebulizadores', 'accesorios', 'cristales', 'libros',
  'kits', 'otro',
]

function formatCurrency(n?: number) {
  if (!n && n !== 0) return '—'
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n)
}

const emptyForm = {
  nombre: '',
  descripcion: '',
  categoria: '',
  precio_minorista: '',
  precio_mayorista: '',
  stock: '',
  activo: true,
  destacado: false,
}

export default function CatalogPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [showDialog, setShowDialog] = useState(false)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  // PDF Export dialog
  const [showPdfDialog, setShowPdfDialog] = useState(false)
  const [pdfTitle, setPdfTitle] = useState('Catálogo Kairos')
  const [selectedForPdf, setSelectedForPdf] = useState<Set<number>>(new Set())

  useEffect(() => {
    getProducts()
      .then((data) => setProducts(data.items ?? data ?? []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const openAddDialog = () => {
    setEditingProduct(null)
    setForm(emptyForm)
    setShowDialog(true)
  }

  const openEditDialog = (product: Product) => {
    setEditingProduct(product)
    setForm({
      nombre: product.nombre,
      descripcion: product.descripcion ?? '',
      categoria: product.categoria ?? '',
      precio_minorista: String(product.precio_minorista ?? ''),
      precio_mayorista: String(product.precio_mayorista ?? ''),
      stock: String(product.stock ?? ''),
      activo: product.activo ?? true,
      destacado: product.destacado ?? false,
    })
    setShowDialog(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const payload = {
        nombre: form.nombre,
        descripcion: form.descripcion || undefined,
        categoria: form.categoria || undefined,
        precio_minorista: form.precio_minorista ? parseFloat(form.precio_minorista) : undefined,
        precio_mayorista: form.precio_mayorista ? parseFloat(form.precio_mayorista) : undefined,
        stock: form.stock ? parseInt(form.stock) : undefined,
        activo: form.activo,
        destacado: form.destacado,
      }
      if (editingProduct) {
        const updated = await updateProduct(editingProduct.id, payload)
        setProducts((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
      } else {
        const created = await createProduct(payload)
        setProducts((prev) => [created, ...prev])
      }
      setShowDialog(false)
    } catch {
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async (product: Product, field: 'activo' | 'destacado') => {
    try {
      const updated = await updateProduct(product.id, { [field]: !product[field] })
      setProducts((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
    } catch {}
  }

  const handleExportPdf = () => {
    const ids = Array.from(selectedForPdf)
    const params = new URLSearchParams({ title: pdfTitle })
    if (ids.length > 0) {
      ids.forEach((id) => params.append('product_ids', String(id)))
    }
    window.open(`${getApiUrl('/products/export-catalog')}?${params.toString()}`, '_blank')
    setShowPdfDialog(false)
  }

  const togglePdfProduct = (id: number) => {
    const next = new Set(selectedForPdf)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelectedForPdf(next)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Catálogo</h1>
          <p className="text-slate-500 mt-1">{products.length} productos</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setSelectedForPdf(new Set(products.map((p) => p.id)))
              setShowPdfDialog(true)
            }}
            className="gap-2"
          >
            <FileDown className="w-4 h-4" />
            Exportar PDF
          </Button>
          <Button onClick={openAddDialog} className="gap-2">
            <Plus className="w-4 h-4" />
            Agregar Producto
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
        </div>
      ) : products.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <Package className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <p>No hay productos en el catálogo</p>
          <Button onClick={openAddDialog} className="mt-4">Agregar primer producto</Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {products.map((product) => (
            <Card
              key={product.id}
              className={`relative overflow-hidden ${product.activo === false ? 'opacity-60' : ''}`}
            >
              {/* Image Placeholder */}
              <div className="bg-gradient-to-br from-slate-100 to-slate-200 h-36 flex items-center justify-center">
                {product.imagen_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={product.imagen_url}
                    alt={product.nombre}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <Package className="w-10 h-10 text-slate-300" />
                )}
                {product.destacado && (
                  <div className="absolute top-2 right-2 bg-amber-400 text-white rounded-full p-1">
                    <Star className="w-3.5 h-3.5" />
                  </div>
                )}
              </div>

              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-slate-900 truncate">{product.nombre}</p>
                    {product.categoria && (
                      <p className="text-xs text-slate-500 capitalize mt-0.5">{product.categoria}</p>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="flex-shrink-0 h-8 w-8"
                    onClick={() => openEditDialog(product)}
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </Button>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2">
                  <div className="bg-slate-50 rounded p-2">
                    <p className="text-xs text-slate-500">Minorista</p>
                    <p className="text-sm font-semibold text-slate-900">
                      {formatCurrency(product.precio_minorista)}
                    </p>
                  </div>
                  <div className="bg-blue-50 rounded p-2">
                    <p className="text-xs text-blue-600">Mayorista</p>
                    <p className="text-sm font-semibold text-blue-900">
                      {formatCurrency(product.precio_mayorista)}
                    </p>
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {product.stock !== undefined && (
                      <Badge
                        variant={
                          product.stock === 0 ? 'danger' : product.stock < 5 ? 'warning' : 'success'
                        }
                      >
                        Stock: {product.stock}
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      className="text-xs text-slate-500 flex items-center gap-1"
                      onClick={() => handleToggle(product, 'destacado')}
                    >
                      <Star
                        className={`w-3.5 h-3.5 ${product.destacado ? 'fill-amber-400 text-amber-400' : 'text-slate-300'}`}
                      />
                    </button>
                    <Switch
                      checked={product.activo !== false}
                      onCheckedChange={() => handleToggle(product, 'activo')}
                      className="scale-75"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add / Edit Product Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingProduct ? 'Editar Producto' : 'Nuevo Producto'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1.5">
              <Label>Nombre *</Label>
              <Input
                value={form.nombre}
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
                placeholder="Aceite Esencial de Lavanda"
              />
            </div>

            <div className="space-y-1.5">
              <Label>Categoría</Label>
              <Select value={form.categoria} onValueChange={(v) => setForm({ ...form, categoria: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar..." />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIAS.map((c) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>Descripción</Label>
              <Textarea
                value={form.descripcion}
                onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
                placeholder="Descripción del producto..."
                rows={2}
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label>P. Minorista</Label>
                <Input
                  type="number"
                  value={form.precio_minorista}
                  onChange={(e) => setForm({ ...form, precio_minorista: e.target.value })}
                  placeholder="0"
                />
              </div>
              <div className="space-y-1.5">
                <Label>P. Mayorista</Label>
                <Input
                  type="number"
                  value={form.precio_mayorista}
                  onChange={(e) => setForm({ ...form, precio_mayorista: e.target.value })}
                  placeholder="0"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Stock</Label>
                <Input
                  type="number"
                  value={form.stock}
                  onChange={(e) => setForm({ ...form, stock: e.target.value })}
                  placeholder="0"
                />
              </div>
            </div>

            <div className="flex items-center gap-6 pt-2">
              <div className="flex items-center gap-2">
                <Switch
                  id="activo"
                  checked={form.activo}
                  onCheckedChange={(v) => setForm({ ...form, activo: v })}
                />
                <Label htmlFor="activo">Activo</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  id="destacado"
                  checked={form.destacado}
                  onCheckedChange={(v) => setForm({ ...form, destacado: v })}
                />
                <Label htmlFor="destacado">Destacado</Label>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)}>Cancelar</Button>
            <Button onClick={handleSave} disabled={!form.nombre.trim() || saving}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              {editingProduct ? 'Guardar' : 'Crear'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* PDF Export Dialog */}
      <Dialog open={showPdfDialog} onOpenChange={setShowPdfDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Exportar Catálogo PDF</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label>Título del catálogo</Label>
              <Input
                value={pdfTitle}
                onChange={(e) => setPdfTitle(e.target.value)}
                placeholder="Catálogo Kairos"
              />
            </div>
            <div className="space-y-2">
              <Label>Seleccionar productos ({selectedForPdf.size} seleccionados)</Label>
              <div className="max-h-48 overflow-y-auto space-y-1 border rounded-md p-2">
                {products.map((p) => (
                  <label key={p.id} className="flex items-center gap-2 cursor-pointer py-1">
                    <input
                      type="checkbox"
                      checked={selectedForPdf.has(p.id)}
                      onChange={() => togglePdfProduct(p.id)}
                      className="rounded"
                    />
                    <span className="text-sm">{p.nombre}</span>
                  </label>
                ))}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedForPdf(new Set(products.map((p) => p.id)))}
                >
                  Todos
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedForPdf(new Set())}
                >
                  Ninguno
                </Button>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowPdfDialog(false)}>Cancelar</Button>
            <Button onClick={handleExportPdf} disabled={selectedForPdf.size === 0} className="gap-2">
              <FileDown className="w-4 h-4" />
              Descargar PDF
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

'use client'

import { useEffect, useState, useRef } from 'react'
import { getProducts, createProduct, updateProduct, getApiUrl, sendCatalogueToClients, scrapeKairosdis, getKairosdisScraperStatus } from '@/lib/api'
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
import { Plus, Loader2, Package, Pencil, Star, FileDown, Upload, Users, Globe } from 'lucide-react'

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
  imagen_url: '',
}

function ImageUploader({ value, onChange }: { value: string; onChange: (url: string) => void }) {
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = (file: File) => {
    const canvas = document.createElement('canvas')
    const img = document.createElement('img')
    const reader = new FileReader()
    reader.onload = (e) => {
      img.onload = () => {
        const MAX = 800
        let { width, height } = img
        if (width > MAX || height > MAX) {
          if (width > height) { height = (height / width) * MAX; width = MAX }
          else { width = (width / height) * MAX; height = MAX }
        }
        canvas.width = width; canvas.height = height
        canvas.getContext('2d')!.drawImage(img, 0, 0, width, height)
        onChange(canvas.toDataURL('image/jpeg', 0.75))
      }
      img.src = e.target?.result as string
    }
    reader.readAsDataURL(file)
  }

  return (
    <div className="space-y-1.5">
      <Label>Imagen del producto</Label>
      <div
        className="h-32 border-2 border-dashed rounded-lg flex items-center justify-center cursor-pointer hover:bg-slate-50 transition-colors overflow-hidden relative"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f?.type.startsWith('image/')) handleFile(f) }}
      >
        {value ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={value} alt="preview" className="h-full w-full object-contain" />
        ) : (
          <div className="text-center text-slate-400">
            <Upload className="w-6 h-6 mx-auto mb-1" />
            <p className="text-xs">Click o arrastrá una imagen</p>
          </div>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
      />
      {value && (
        <Button type="button" variant="ghost" size="sm" className="text-red-500 h-7 px-2"
          onClick={(e) => { e.stopPropagation(); onChange('') }}>
          Eliminar imagen
        </Button>
      )}
    </div>
  )
}

export default function CatalogPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCategory, setSelectedCategory] = useState('')
  const [categories, setCategories] = useState<string[]>([])
  const [showDialog, setShowDialog] = useState(false)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [notifying, setNotifying] = useState(false)
  const [notifyResult, setNotifyResult] = useState('')

  // Kairosdis scraper
  const [scraping, setScraping] = useState(false)
  const [scrapeJob, setScrapeJob] = useState<{
    status: string; progress: number; total: number; new: number; updated: number; errors: string[]
  } | null>(null)

  // PDF Export dialog
  const [showPdfDialog, setShowPdfDialog] = useState(false)
  const [pdfTitle, setPdfTitle] = useState('Catálogo Kairos')
  const [selectedForPdf, setSelectedForPdf] = useState<Set<number>>(new Set())

  useEffect(() => {
    getProducts()
      .then((data) => {
        const items: Product[] = data.items ?? data ?? []
        setProducts(items)
        const cats = Array.from(new Set(items.map((p) => p.categoria).filter(Boolean))) as string[]
        setCategories(cats)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!scraping) return
    const interval = setInterval(async () => {
      try {
        const job = await getKairosdisScraperStatus()
        setScrapeJob(job)
        if (job.status === 'completed' || job.status === 'error') {
          setScraping(false)
          clearInterval(interval)
          // Reload products after successful import
          if (job.status === 'completed') {
            getProducts()
              .then((data) => {
                const items: Product[] = data.items ?? data ?? []
                setProducts(items)
                const cats = Array.from(new Set(items.map((p) => p.categoria).filter(Boolean))) as string[]
                setCategories(cats)
              })
              .catch(() => {})
          }
        }
      } catch {
        setScraping(false)
        clearInterval(interval)
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [scraping])

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
      imagen_url: product.imagen_url ?? '',
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
        imagen_url: form.imagen_url || undefined,
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

  const filteredProducts = selectedCategory
    ? products.filter((p) => p.categoria === selectedCategory)
    : products

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Catálogo</h1>
          <p className="text-slate-500 mt-1">{filteredProducts.length} productos</p>
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
          <Button
            variant="outline"
            onClick={async () => {
              setNotifying(true)
              try {
                const r = await sendCatalogueToClients()
                setNotifyResult(`✓ Catálogo enviado a ${r.queued} clientes`)
                setTimeout(() => setNotifyResult(''), 5000)
              } catch { setNotifyResult('Error al enviar') }
              finally { setNotifying(false) }
            }}
            disabled={notifying}
            className="gap-2"
          >
            {notifying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Users className="w-4 h-4" />}
            {notifying ? 'Enviando...' : 'Notificar Clientes'}
          </Button>
          <Button
            variant="outline"
            onClick={async () => {
              setScraping(true)
              setScrapeJob(null)
              try {
                await scrapeKairosdis()
              } catch {
                setScraping(false)
              }
            }}
            disabled={scraping}
            className="gap-2"
          >
            {scraping ? <Loader2 className="w-4 h-4 animate-spin" /> : <Globe className="w-4 h-4" />}
            {scraping
              ? scrapeJob
                ? `${scrapeJob.progress}% — ${scrapeJob.status}`
                : 'Iniciando...'
              : 'Importar Kairosdis'}
          </Button>
          <Button onClick={openAddDialog} className="gap-2">
            <Plus className="w-4 h-4" />
            Agregar Producto
          </Button>
        </div>
      </div>
      {notifyResult && (
        <p className={`text-sm font-medium -mt-3 ${notifyResult.startsWith('✓') ? 'text-green-600' : 'text-red-500'}`}>
          {notifyResult}
        </p>
      )}
      {scrapeJob && (scrapeJob.status === 'completed' || scrapeJob.status === 'error') && (
        <p className={`text-sm font-medium -mt-3 ${scrapeJob.status === 'completed' ? 'text-green-600' : 'text-red-500'}`}>
          {scrapeJob.status === 'completed'
            ? `✓ Kairosdis importado: ${scrapeJob.new} nuevos, ${scrapeJob.updated} actualizados de ${scrapeJob.total} productos`
            : `✗ Error al importar Kairosdis${scrapeJob.errors[0] ? ': ' + scrapeJob.errors[0] : ''}`}
        </p>
      )}

      {categories.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSelectedCategory('')}
            className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${selectedCategory === '' ? 'text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            style={selectedCategory === '' ? { backgroundColor: '#4A3728' } : {}}
          >
            Todos
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1 rounded-full text-sm font-medium capitalize transition-colors ${selectedCategory === cat ? 'text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
              style={selectedCategory === cat ? { backgroundColor: '#C9A040' } : {}}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
        </div>
      ) : filteredProducts.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <Package className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <p>{products.length === 0 ? 'No hay productos en el catálogo' : 'No hay productos en esta categoría'}</p>
          {products.length === 0 && <Button onClick={openAddDialog} className="mt-4">Agregar primer producto</Button>}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredProducts.map((product) => (
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
            <ImageUploader value={form.imagen_url} onChange={(v) => setForm({ ...form, imagen_url: v })} />

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

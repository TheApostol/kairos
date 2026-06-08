'use client'

import { useEffect, useState } from 'react'
import { getProducts, getProductCategories, createProduct, updateProduct, getApiUrl, sendCatalogueToClients, scrapeKairosdis, getKairosdisScraperStatus, syncFromGoogleSheet, getProductsCsvUrl, getSheetConfig, setSheetId, exportCatalogToSheet } from '@/lib/api'
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
import { Plus, Loader2, Package, Pencil, Star, FileDown, Upload, Users, Globe, ChevronLeft, ChevronRight, Sheet, RefreshCw, Link2, CheckCircle2, Copy, Check } from 'lucide-react'

const PER_PAGE = 24

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
  const inputRef = useState<HTMLInputElement | null>(null)

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
        onClick={() => (inputRef[0] as HTMLInputElement | null)?.click()}
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
        ref={(el) => { (inputRef as unknown as { current: HTMLInputElement | null }).current = el }}
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
  const [categories, setCategories] = useState<string[]>([])
  const [selectedCategory, setSelectedCategory] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [productRefresh, setProductRefresh] = useState(0)

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
  const [allProductsForPdf, setAllProductsForPdf] = useState<Product[]>([])
  const [loadingPdfProducts, setLoadingPdfProducts] = useState(false)
  const [exportAllProducts, setExportAllProducts] = useState(true)
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [pdfError, setPdfError] = useState('')

  const [copied, setCopied] = useState(false)

  // Google Sheets sync
  const [sheetSyncing, setSheetSyncing] = useState(false)
  const [sheetSyncResult, setSheetSyncResult] = useState('')
  const [sheetId, setSheetIdState] = useState('')
  const [sheetInput, setSheetInput] = useState('')
  const [showSheetConfig, setShowSheetConfig] = useState(false)
  const [savingSheet, setSavingSheet] = useState(false)
  const [exportingToSheet, setExportingToSheet] = useState(false)
  const [lastSync, setLastSync] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<{created:number,updated:number,skipped:number}|null>(null)

  const copyPublicCatalog = () => {
    const url = `${window.location.origin}/public/catalog?tipo=mayorista`
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  // Load category list + sheet config on mount
  useEffect(() => {
    getProductCategories()
      .then((data) => setCategories(data.categories ?? []))
      .catch(() => {})
    getSheetConfig()
      .then((cfg) => {
        if (cfg?.sheet_id) { setSheetIdState(cfg.sheet_id); setSheetInput(cfg.sheet_id) }
        if (cfg?.last_sync) setLastSync(cfg.last_sync)
        if (cfg?.last_result) setLastResult(cfg.last_result)
      })
      .catch(() => {})
  }, [])

  // Load products when page, category or refresh key changes
  useEffect(() => {
    setLoading(true)
    const params: Record<string, string> = {
      page: String(currentPage),
      per_page: String(PER_PAGE),
    }
    if (selectedCategory) params.categoria = selectedCategory

    getProducts(params)
      .then((data) => {
        setProducts(data.items ?? data ?? [])
        setTotalPages(data.pages ?? 1)
        setTotalCount(data.total ?? 0)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [currentPage, selectedCategory, productRefresh])

  // Poll scraper status
  useEffect(() => {
    if (!scraping) return
    const interval = setInterval(async () => {
      try {
        const job = await getKairosdisScraperStatus()
        setScrapeJob(job)
        if (job.status === 'completed' || job.status === 'error') {
          setScraping(false)
          clearInterval(interval)
          if (job.status === 'completed') {
            setCurrentPage(1)
            setProductRefresh((r) => r + 1)
          }
        }
      } catch {
        setScraping(false)
        clearInterval(interval)
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [scraping])

  const handleCategoryChange = (cat: string) => {
    setSelectedCategory(cat)
    setCurrentPage(1)
  }

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
        await createProduct(payload)
        setProductRefresh((r) => r + 1)
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

  const handleExportPdf = async () => {
    setDownloadingPdf(true)
    setPdfError('')
    const params = new URLSearchParams({ title: pdfTitle })
    if (!exportAllProducts) {
      const ids = Array.from(selectedForPdf)
      if (ids.length === 0) { setDownloadingPdf(false); return }
      ids.forEach((id) => params.append('product_ids', String(id)))
    }
    try {
      const res = await fetch(`${getApiUrl('/products/export-catalog')}?${params.toString()}`)
      if (!res.ok) throw new Error(await res.text())
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `catalogo_kairos_${new Date().toISOString().slice(0,10)}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      setShowPdfDialog(false)
    } catch (e) {
      setPdfError(e instanceof Error ? e.message : 'Error al generar el PDF')
    } finally {
      setDownloadingPdf(false)
    }
  }

  const togglePdfProduct = (id: number) => {
    const next = new Set(selectedForPdf)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelectedForPdf(next)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Catálogo</h1>
          <p className="text-slate-500 mt-1">
            {totalCount > 0 ? `${totalCount.toLocaleString('es-AR')} productos` : 'Sin productos'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={async () => {
              setShowPdfDialog(true)
              setPdfError('')
              setExportAllProducts(true)
              setLoadingPdfProducts(true)
              try {
                const data = await getProducts({ per_page: '500', activo: 'true' })
                const all: Product[] = data.items ?? data ?? []
                setAllProductsForPdf(all)
                setSelectedForPdf(new Set(all.map((p: Product) => p.id)))
              } catch {
                setAllProductsForPdf(products)
                setSelectedForPdf(new Set(products.map((p) => p.id)))
              } finally {
                setLoadingPdfProducts(false)
              }
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
              try { await scrapeKairosdis() } catch { setScraping(false) }
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
          <Button
            variant="outline"
            onClick={() => window.open(getProductsCsvUrl(), '_blank')}
            className="gap-2"
          >
            <Sheet className="w-4 h-4" />
            Exportar CSV
          </Button>
          <Button
            variant="outline"
            onClick={async () => {
              setSheetSyncing(true)
              setSheetSyncResult('')
              try {
                const r = await syncFromGoogleSheet()
                const msg = `✓ ${r.created ?? 0} creados, ${r.updated ?? 0} actualizados${r.errors?.length ? `, ${r.errors.length} errores` : ''}`
                setSheetSyncResult(msg)
                setLastSync(new Date().toISOString())
                setLastResult(r)
                setProductRefresh((n) => n + 1)
              } catch (e: unknown) {
                setSheetSyncResult(`Error: ${e instanceof Error ? e.message : 'Sin hoja configurada'}`)
              } finally {
                setSheetSyncing(false)
                setTimeout(() => setSheetSyncResult(''), 6000)
              }
            }}
            disabled={sheetSyncing || !sheetId}
            className="gap-2"
            title={!sheetId ? 'Configurá el Google Sheet primero' : ''}
          >
            {sheetSyncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            {sheetSyncing ? 'Sincronizando...' : 'Sync ahora'}
          </Button>
          {sheetId && (
            <Button
              variant="outline"
              onClick={async () => {
                setExportingToSheet(true)
                setSheetSyncResult('')
                try {
                  const r = await exportCatalogToSheet()
                  setSheetSyncResult(`✓ ${r.exported ?? 0} productos exportados al Sheet`)
                } catch (e: unknown) {
                  setSheetSyncResult(`Error: ${e instanceof Error ? e.message : 'No se pudo exportar'}`)
                } finally {
                  setExportingToSheet(false)
                  setTimeout(() => setSheetSyncResult(''), 6000)
                }
              }}
              disabled={exportingToSheet}
              className="gap-2"
              title="Escribe todos los productos actuales en la planilla de Google Sheets"
            >
              {exportingToSheet ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              {exportingToSheet ? 'Exportando...' : 'Poblar Sheet'}
            </Button>
          )}
          <Button
            variant="outline"
            onClick={() => setShowSheetConfig(true)}
            className={`gap-2 ${sheetId ? 'border-green-500 text-green-700' : 'border-dashed'}`}
          >
            {sheetId ? <CheckCircle2 className="w-4 h-4 text-green-600" /> : <Link2 className="w-4 h-4" />}
            {sheetId ? 'Sheet conectado' : 'Conectar Google Sheet'}
          </Button>
          <Button
            variant="outline"
            onClick={copyPublicCatalog}
            className="gap-2"
            title="Copiar link público del catálogo mayorista"
          >
            {copied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
            {copied ? 'Copiado!' : 'Link público'}
          </Button>
          <Button onClick={openAddDialog} className="gap-2">
            <Plus className="w-4 h-4" />
            Agregar Producto
          </Button>
        </div>
      </div>

      {/* Status messages */}
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
      {sheetSyncResult && (
        <p className={`text-sm font-medium -mt-3 ${sheetSyncResult.startsWith('✓') ? 'text-green-600' : 'text-red-500'}`}>
          {sheetSyncResult}
        </p>
      )}
      {!sheetSyncResult && sheetId && lastSync && (
        <p className="text-xs text-slate-400 -mt-3">
          <CheckCircle2 className="inline w-3 h-3 text-green-500 mr-1" />
          Sync automático activo · Último sync: {new Date(lastSync).toLocaleString('es-AR')}
          {lastResult && ` · ${lastResult.created ?? 0} creados, ${lastResult.updated ?? 0} actualizados`}
        </p>
      )}
      {!sheetId && (
        <p className="text-xs text-amber-600 -mt-3">
          Sin Google Sheet configurado — los productos se gestionan manualmente.
        </p>
      )}

      {/* Category filter */}
      {categories.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => handleCategoryChange('')}
            className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${selectedCategory === '' ? 'text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            style={selectedCategory === '' ? { backgroundColor: '#4A3728' } : {}}
          >
            Todos
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => handleCategoryChange(cat)}
              className={`px-3 py-1 rounded-full text-sm font-medium capitalize transition-colors ${selectedCategory === cat ? 'text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
              style={selectedCategory === cat ? { backgroundColor: '#C9A040' } : {}}
            >
              {cat.replace(/-/g, ' ')}
            </button>
          ))}
        </div>
      )}

      {/* Product grid */}
      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
        </div>
      ) : products.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <Package className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <p>{totalCount === 0 ? 'No hay productos en el catálogo' : 'No hay productos en esta categoría'}</p>
          {totalCount === 0 && <Button onClick={openAddDialog} className="mt-4">Agregar primer producto</Button>}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {products.map((product) => (
            <Card
              key={product.id}
              className={`relative overflow-hidden ${product.activo === false ? 'opacity-60' : ''}`}
            >
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
                    <p className="font-semibold text-slate-900 truncate text-sm">{product.nombre}</p>
                    {product.categoria && (
                      <p className="text-xs text-slate-500 capitalize mt-0.5">{product.categoria.replace(/-/g, ' ')}</p>
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

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="gap-1"
          >
            <ChevronLeft className="w-4 h-4" />
            Anterior
          </Button>
          <span className="text-sm text-slate-600 min-w-[140px] text-center">
            Página {currentPage} de {totalPages}
            <span className="text-slate-400 ml-1">({totalCount.toLocaleString('es-AR')} total)</span>
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className="gap-1"
          >
            Siguiente
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      )}

      {/* Add / Edit Product Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-lg max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>{editingProduct ? 'Editar Producto' : 'Nuevo Producto'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2 overflow-y-auto flex-1 pr-1">
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

            {/* Export scope toggle */}
            <div className="space-y-2">
              <Label>Productos a incluir</Label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setExportAllProducts(true)}
                  className={`flex-1 py-2 px-3 rounded-md border text-sm font-medium transition-colors ${exportAllProducts ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'}`}
                >
                  Todo el catálogo
                  {!loadingPdfProducts && allProductsForPdf.length > 0 && (
                    <span className="ml-1 opacity-70">({allProductsForPdf.length})</span>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => setExportAllProducts(false)}
                  className={`flex-1 py-2 px-3 rounded-md border text-sm font-medium transition-colors ${!exportAllProducts ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'}`}
                >
                  Selección manual
                </button>
              </div>
            </div>

            {/* Manual selection list */}
            {!exportAllProducts && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>{selectedForPdf.size} seleccionados</Label>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" className="h-6 text-xs"
                      onClick={() => setSelectedForPdf(new Set(allProductsForPdf.map((p) => p.id)))}>
                      Todos
                    </Button>
                    <Button variant="ghost" size="sm" className="h-6 text-xs"
                      onClick={() => setSelectedForPdf(new Set())}>
                      Ninguno
                    </Button>
                  </div>
                </div>
                {loadingPdfProducts ? (
                  <div className="flex items-center justify-center h-24 border rounded-md">
                    <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
                  </div>
                ) : (
                  <div className="max-h-48 overflow-y-auto space-y-0.5 border rounded-md p-2">
                    {allProductsForPdf.map((p) => (
                      <label key={p.id} className="flex items-center gap-2 cursor-pointer py-1 hover:bg-slate-50 px-1 rounded">
                        <input
                          type="checkbox"
                          checked={selectedForPdf.has(p.id)}
                          onChange={() => togglePdfProduct(p.id)}
                          className="rounded"
                        />
                        <span className="text-sm truncate">{p.nombre}</span>
                        {p.categoria && <span className="text-xs text-slate-400 ml-auto shrink-0">{p.categoria}</span>}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
          {pdfError && (
            <p className="text-sm text-red-600 px-1">{pdfError}</p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowPdfDialog(false); setPdfError('') }}>Cancelar</Button>
            <Button
              onClick={handleExportPdf}
              disabled={((!exportAllProducts && selectedForPdf.size === 0) || downloadingPdf)}
              className="gap-2"
            >
              {downloadingPdf ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileDown className="w-4 h-4" />}
              {downloadingPdf ? 'Generando...' : `Descargar PDF${exportAllProducts && allProductsForPdf.length > 0 ? ` (${allProductsForPdf.length})` : ''}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Google Sheet Config Dialog */}
      <Dialog open={showSheetConfig} onOpenChange={setShowSheetConfig}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sheet className="w-5 h-5 text-green-600" />
              Conectar Google Sheet al Catálogo
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800 space-y-1">
              <p className="font-semibold">¿Cómo funciona?</p>
              <p>Al conectar, el sistema escribe todos los productos actuales en la planilla automáticamente. Después, cualquier cambio que hagas en la planilla se sincroniza al catálogo cada 10 minutos.</p>
            </div>
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 space-y-1">
              <p className="font-semibold">Requisito para auto-poblar la planilla</p>
              <p>Para que el sistema pueda <em>escribir</em> en la planilla necesita una cuenta de servicio de Google (variable <code>GOOGLE_SERVICE_ACCOUNT_JSON</code> en el servidor). Compartí la planilla con el email de esa cuenta de servicio como Editor.</p>
              <p>Sin cuenta de servicio, el sistema solo <em>lee</em> de la planilla — tenés que poblarla manualmente exportando el CSV desde el Catálogo.</p>
            </div>
            <div className="space-y-2 text-sm">
              <p className="font-medium text-slate-700">Columnas de la planilla:</p>
              <div className="rounded-md bg-slate-50 border p-3 font-mono text-xs text-slate-600 overflow-x-auto whitespace-nowrap">
                ID · SKU · Nombre* · Categoría · Descripción · Precio Minorista · Precio Mayorista · Precio Promo · Stock · Activo · Imagen URL
              </div>
              <p className="text-slate-500">
                * Solo <strong>Nombre</strong> es obligatorio para crear un producto nuevo.<br />
                La planilla debe estar compartida como <strong>"Cualquiera con el link puede ver"</strong> (o con la cuenta de servicio como Editor).
              </p>
            </div>
            <div className="space-y-1.5">
              <Label>URL o ID de la planilla</Label>
              <Input
                value={sheetInput}
                onChange={(e) => setSheetInput(e.target.value)}
                placeholder="https://docs.google.com/spreadsheets/d/... o solo el ID"
              />
              <p className="text-xs text-slate-400">Acepta la URL completa — extrae el ID automáticamente.</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSheetConfig(false)}>Cancelar</Button>
            <Button
              disabled={!sheetInput.trim() || savingSheet}
              onClick={async () => {
                setSavingSheet(true)
                try {
                  const r = await setSheetId(sheetInput.trim())
                  setSheetIdState(r.sheet_id ?? sheetInput.trim())
                  setLastSync(new Date().toISOString())
                  setLastResult(r)
                  setProductRefresh((n) => n + 1)
                  setShowSheetConfig(false)
                  const exportedMsg = r.exported != null ? ` · ${r.exported} productos escritos en la planilla` : ''
                  setSheetSyncResult(`✓ Sheet conectado${exportedMsg} · ${r.created ?? 0} creados, ${r.updated ?? 0} actualizados`)
                  setTimeout(() => setSheetSyncResult(''), 6000)
                } catch (e: unknown) {
                  setSheetSyncResult(`Error: ${e instanceof Error ? e.message : 'No se pudo conectar la hoja'}`)
                  setTimeout(() => setSheetSyncResult(''), 6000)
                } finally {
                  setSavingSheet(false)
                }
              }}
              className="gap-2"
            >
              {savingSheet ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              {savingSheet ? 'Conectando...' : 'Guardar y sincronizar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

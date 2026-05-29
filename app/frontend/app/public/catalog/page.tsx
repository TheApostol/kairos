'use client'

import { useEffect, useState } from 'react'
import { Package } from 'lucide-react'

interface Product {
  id: number
  nombre: string
  descripcion?: string
  categoria?: string
  precio_minorista?: number
  precio_mayorista?: number
  stock?: number
  imagen_url?: string
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://kairos-anuu.onrender.com'

function formatCurrency(n?: number) {
  if (n === undefined || n === null) return 'Consultar'
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    maximumFractionDigits: 0,
  }).format(n)
}

function StockBadge({ stock }: { stock?: number }) {
  if (stock === undefined || stock === null) return null
  if (stock === 0) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
        Sin stock
      </span>
    )
  }
  if (stock <= 5) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
        Últimas {stock}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
      Disponible
    </span>
  )
}

export default function PublicCatalogPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [isMayorista, setIsMayorista] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const tipo = params.get('tipo')
    setIsMayorista(tipo === 'mayorista')

    fetch(`${API_URL}/products?activo=true`)
      .then((r) => r.json())
      .then((data) => setProducts(data.items ?? data ?? []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const today = new Date().toLocaleDateString('es-AR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FAF7F4' }}>
      {/* Header */}
      <header className="sticky top-0 z-10 shadow-sm" style={{ backgroundColor: '#FAF7F4', borderBottom: '1px solid #E8DDD5' }}>
        <div className="max-w-5xl mx-auto px-4 py-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div>
              <h1 className="text-2xl font-bold tracking-tight" style={{ color: '#4A3728' }}>
                Kairos
              </h1>
              <p className="text-sm mt-0.5" style={{ color: '#6B4F3A' }}>
                Catálogo de Productos
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs" style={{ color: '#6B4F3A' }}>{today}</span>
              {!loading && (
                <span
                  className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold"
                  style={{ backgroundColor: '#C9A040', color: '#fff' }}
                >
                  {products.length} productos
                </span>
              )}
              {isMayorista && (
                <span
                  className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold"
                  style={{ backgroundColor: '#4A3728', color: '#fff' }}
                >
                  Mayorista
                </span>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-5xl mx-auto px-4 py-6">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 gap-3">
            <div
              className="w-8 h-8 rounded-full border-2 border-t-transparent animate-spin"
              style={{ borderColor: '#C9A040', borderTopColor: 'transparent' }}
            />
            <p className="text-sm" style={{ color: '#6B4F3A' }}>Cargando catálogo...</p>
          </div>
        ) : products.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 gap-3">
            <Package className="w-12 h-12 opacity-30" style={{ color: '#6B4F3A' }} />
            <p className="text-sm" style={{ color: '#6B4F3A' }}>No hay productos disponibles</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {products.map((product) => {
              const price = isMayorista ? product.precio_mayorista : product.precio_minorista
              const priceLabel = isMayorista ? 'Mayorista' : 'Precio'

              return (
                <div
                  key={product.id}
                  className="rounded-xl overflow-hidden shadow-sm flex flex-col"
                  style={{ backgroundColor: '#fff', border: '1px solid #E8DDD5' }}
                >
                  {/* Image */}
                  <div
                    className="relative h-36 flex items-center justify-center overflow-hidden"
                    style={{
                      background: product.imagen_url
                        ? undefined
                        : 'linear-gradient(135deg, #E8DDD5 0%, #D4C4B8 100%)',
                    }}
                  >
                    {product.imagen_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={product.imagen_url}
                        alt={product.nombre}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <Package className="w-10 h-10 opacity-30" style={{ color: '#6B4F3A' }} />
                    )}
                  </div>

                  {/* Card body */}
                  <div className="p-3 flex flex-col gap-1 flex-1">
                    <p className="font-semibold text-sm leading-tight" style={{ color: '#2D1F17' }}>
                      {product.nombre}
                    </p>
                    {product.categoria && (
                      <p className="text-xs capitalize" style={{ color: '#64748B' }}>
                        {product.categoria}
                      </p>
                    )}
                    {product.descripcion && (
                      <p
                        className="text-xs leading-snug mt-0.5"
                        style={{
                          color: '#475569',
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        }}
                      >
                        {product.descripcion}
                      </p>
                    )}

                    {/* Price and stock */}
                    <div className="mt-auto pt-2 flex items-end justify-between gap-1 flex-wrap">
                      <div>
                        <p className="text-xs" style={{ color: '#6B4F3A' }}>{priceLabel}</p>
                        <p className="text-sm font-bold" style={{ color: '#4A3728' }}>
                          {price !== undefined && price !== null ? formatCurrency(price) : 'Consultar'}
                        </p>
                      </div>
                      <StockBadge stock={product.stock} />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="mt-8 py-5 text-center text-xs" style={{ color: '#6B4F3A', borderTop: '1px solid #E8DDD5' }}>
        Kairos · Precios en ARS · Sujeto a cambio sin previo aviso
      </footer>
    </div>
  )
}

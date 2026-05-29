'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { getLeads, updateLead, runScraper } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Building2, Search, Loader2, Play, ChevronLeft, ChevronRight } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

interface Mayorista {
  id: string
  empresa: string
  rubro?: string
  ciudad?: string
  provincia?: string
  telefono?: string
  email?: string
  website?: string
  estado: string
  score_ia?: number
  score?: number
  created_at?: string
  tipo_cliente: string
}

function EstadoBadge({ estado }: { estado: string }) {
  const map: Record<string, 'success' | 'info' | 'warning' | 'gray' | 'secondary'> = {
    cliente: 'success',
    interesado: 'info',
    contactado: 'warning',
    nuevo: 'gray',
    descartado: 'secondary',
  }
  return <Badge variant={map[estado] ?? 'secondary'} className="capitalize">{estado}</Badge>
}

function ScoreBadge({ score }: { score?: number }) {
  if (!score) return <span className="text-slate-400">—</span>
  const color = score >= 7 ? 'text-green-700 bg-green-50' : score >= 4 ? 'text-amber-700 bg-amber-50' : 'text-red-700 bg-red-50'
  return <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${color}`}>{score}</span>
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '—'
  try { return format(new Date(dateStr), "d MMM yyyy", { locale: es }) } catch { return dateStr }
}

export default function MayoristasPage() {
  const router = useRouter()
  const [mayoristas, setMayoristas] = useState<Mayorista[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [search, setSearch] = useState('')
  const [provincia, setProvincia] = useState('')
  const [estado, setEstado] = useState('')
  const [scraping, setScraping] = useState(false)
  const [scrapeMsg, setScrapeMsg] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number | boolean> = {
        tipo_cliente: 'mayorista',
        page,
        limit: 50,
      }
      if (search) params.empresa = search
      if (provincia) params.provincia = provincia
      if (estado) params.estado = estado
      const data = await getLeads(params)
      setMayoristas(data.items ?? data ?? [])
      setTotal(data.total ?? 0)
      setPages(data.pages ?? 1)
    } catch { }
    finally { setLoading(false) }
  }, [page, search, provincia, estado])

  useEffect(() => { load() }, [load])

  const handleEstadoChange = async (id: string, newEstado: string) => {
    try {
      await updateLead(id, { estado: newEstado })
      setMayoristas(prev => prev.map(m => m.id === id ? { ...m, estado: newEstado } : m))
    } catch { }
  }

  const handleScrape = async () => {
    setScraping(true)
    setScrapeMsg('')
    try {
      const res = await runScraper('mayorista')
      setScrapeMsg(`Scraper iniciado (job ${res.job_id}) — ${res.queries_count} búsquedas de mayoristas`)
    } catch (e) {
      setScrapeMsg(e instanceof Error ? e.message : 'Error al iniciar scraper')
    } finally {
      setScraping(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Mayoristas</h1>
          <p className="text-slate-500 mt-1">Distribuidores y clientes mayoristas — {total} registros</p>
        </div>
        <Button
          onClick={handleScrape}
          disabled={scraping}
          className="gap-2 bg-amber-600 hover:bg-amber-700 text-white"
        >
          {scraping ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          Buscar Mayoristas
        </Button>
      </div>

      {scrapeMsg && (
        <div className={`text-sm px-3 py-2 rounded-md ${scrapeMsg.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
          {scrapeMsg}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            placeholder="Buscar empresa..."
            className="pl-9"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
          />
        </div>
        <Select value={provincia || '__all__'} onValueChange={v => { setProvincia(v === '__all__' ? '' : v); setPage(1) }}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Provincia" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">Todas las provincias</SelectItem>
            {['Buenos Aires', 'Ciudad Autónoma de Buenos Aires', 'Córdoba', 'Santa Fe', 'Mendoza', 'Tucumán', 'Salta', 'Neuquén', 'Rosario', 'La Plata'].map(p => (
              <SelectItem key={p} value={p}>{p}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={estado || '__all__'} onValueChange={v => { setEstado(v === '__all__' ? '' : v); setPage(1) }}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Estado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">Todos</SelectItem>
            <SelectItem value="nuevo">Nuevo</SelectItem>
            <SelectItem value="contactado">Contactado</SelectItem>
            <SelectItem value="interesado">Interesado</SelectItem>
            <SelectItem value="cliente">Cliente</SelectItem>
            <SelectItem value="descartado">Descartado</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            </div>
          ) : mayoristas.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-slate-400 gap-3">
              <Building2 className="w-10 h-10 opacity-40" />
              <p>No hay mayoristas todavía</p>
              <Button onClick={handleScrape} size="sm" className="bg-amber-600 hover:bg-amber-700">
                Buscar mayoristas con scraper
              </Button>
            </div>
          ) : (
            <>
              {/* Mobile cards */}
              <div className="sm:hidden divide-y">
                {mayoristas.map(m => (
                  <div
                    key={m.id}
                    className="px-4 py-3 cursor-pointer active:bg-slate-50"
                    onClick={() => router.push(`/leads/${m.id}`)}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-sm truncate text-slate-900">{m.empresa}</p>
                        <p className="text-xs text-slate-500">{[m.ciudad, m.provincia].filter(Boolean).join(', ')}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <EstadoBadge estado={m.estado} />
                          <ScoreBadge score={m.score ?? m.score_ia} />
                        </div>
                      </div>
                      <div className="text-right text-xs text-slate-400">{formatDate(m.created_at)}</div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Desktop table */}
              <div className="hidden sm:block overflow-x-auto">
                <Table className="min-w-[700px]">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Empresa</TableHead>
                      <TableHead>Ciudad</TableHead>
                      <TableHead>Provincia</TableHead>
                      <TableHead>Teléfono</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Score</TableHead>
                      <TableHead>Estado</TableHead>
                      <TableHead>Fecha</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {mayoristas.map(m => (
                      <TableRow
                        key={m.id}
                        className="cursor-pointer"
                        onClick={() => router.push(`/leads/${m.id}`)}
                      >
                        <TableCell className="font-medium text-slate-900">{m.empresa}</TableCell>
                        <TableCell className="text-slate-500">{m.ciudad || '—'}</TableCell>
                        <TableCell className="text-slate-500">{m.provincia || '—'}</TableCell>
                        <TableCell className="text-slate-500">{m.telefono || '—'}</TableCell>
                        <TableCell className="text-slate-500">{m.email || '—'}</TableCell>
                        <TableCell><ScoreBadge score={m.score ?? m.score_ia} /></TableCell>
                        <TableCell onClick={e => e.stopPropagation()}>
                          <Select value={m.estado} onValueChange={v => handleEstadoChange(m.id, v)}>
                            <SelectTrigger className="h-7 text-xs w-32">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {['nuevo', 'contactado', 'interesado', 'cliente', 'descartado'].map(e => (
                                <SelectItem key={e} value={e} className="text-xs capitalize">{e}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell className="text-slate-500">{formatDate(m.created_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              {pages > 1 && (
                <div className="flex items-center justify-between px-4 py-3 border-t text-sm text-slate-500">
                  <span>{total} mayoristas — pág {page}/{pages}</span>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
                      <ChevronLeft className="w-4 h-4" />
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}>
                      <ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
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
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { getLeads, getLeadStats, getLeadRubros, getApiUrl, updateLead } from '@/lib/api'
import { Search, Download, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'

interface Lead {
  id: number
  empresa: string
  ciudad?: string
  provincia?: string
  telefono?: string
  email?: string
  score?: number
  estado?: string
  rubro?: string
  website?: string
}

interface LeadsResponse {
  items: Lead[]
  total: number
  page: number
  pages: number
}


function ScoreBadge({ score }: { score?: number }) {
  if (score === undefined || score === null) return <span className="text-slate-400">—</span>
  if (score >= 7) return <Badge variant="success">{score}</Badge>
  if (score >= 4) return <Badge variant="warning">{score}</Badge>
  return <Badge variant="danger">{score}</Badge>
}

function EstadoBadge({ estado }: { estado?: string }) {
  const variants: Record<string, 'info' | 'warning' | 'orange' | 'success' | 'gray' | 'secondary'> = {
    nuevo: 'info',
    contactado: 'warning',
    interesado: 'orange',
    cliente: 'success',
    descartado: 'gray',
  }
  const labels: Record<string, string> = {
    nuevo: 'Nuevo',
    contactado: 'Contactado',
    interesado: 'Interesado',
    cliente: 'Cliente',
    descartado: 'Descartado',
  }
  const key = estado ?? 'nuevo'
  return <Badge variant={variants[key] ?? 'secondary'}>{labels[key] ?? estado}</Badge>
}

export default function LeadsPage() {
  const router = useRouter()
  const [leads, setLeads] = useState<Lead[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [provincias, setProvincias] = useState<string[]>([])
  const [rubros, setRubros] = useState<string[]>([])

  // Filters
  const [search, setSearch] = useState('')
  const [provincia, setProvincia] = useState('all')
  const [rubro, setRubro] = useState('all')
  const [estado, setEstado] = useState('all')
  const [soloEmail, setSoloEmail] = useState(false)
  const [soloTelefono, setSoloTelefono] = useState(false)

  const fetchLeads = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number | boolean> = {
        page,
        limit: 50,
      }
      if (search) params.empresa = search
      if (provincia && provincia !== 'all') params.provincia = provincia
      if (rubro && rubro !== 'all') params.rubro = rubro
      if (estado && estado !== 'all') params.estado = estado
      if (soloEmail) params.con_email = true
      if (soloTelefono) params.con_telefono = true

      const data: LeadsResponse = await getLeads(params)
      setLeads(data.items ?? [])
      setTotal(data.total ?? 0)
      setPages(data.pages ?? 1)
    } catch {
      setLeads([])
    } finally {
      setLoading(false)
    }
  }, [page, search, provincia, rubro, estado, soloEmail, soloTelefono])

  useEffect(() => {
    fetchLeads()
  }, [fetchLeads])

  useEffect(() => {
    getLeadStats().then((s) => {
      setProvincias((s.por_provincia ?? []).map((p: { provincia: string }) => p.provincia))
    }).catch(() => {})
    getLeadRubros().then((r) => setRubros(r.rubros ?? [])).catch(() => {})
  }, [])

  // Reset page on filter change
  useEffect(() => {
    setPage(1)
  }, [search, provincia, rubro, estado, soloEmail, soloTelefono])

  const handleExport = () => {
    const params = new URLSearchParams()
    if (search) params.set('empresa', search)
    if (provincia && provincia !== 'all') params.set('provincia', provincia)
    if (rubro && rubro !== 'all') params.set('rubro', rubro)
    if (estado && estado !== 'all') params.set('estado', estado)
    if (soloEmail) params.set('con_email', 'true')
    if (soloTelefono) params.set('con_telefono', 'true')
    params.set('format', 'csv')
    window.open(`${getApiUrl('/leads/export')}?${params.toString()}`, '_blank')
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: '#4A3728' }}>Leads</h1>
          <p className="mt-1" style={{ color: '#6B4F3A' }}>{total.toLocaleString('es-AR')} leads en total</p>
        </div>
        <Button onClick={handleExport} variant="outline" className="gap-2">
          <Download className="w-4 h-4" />
          Exportar CSV
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 opacity-50" style={{ color: '#6B4F3A' }} />
              <Input
                placeholder="Buscar empresa..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>

            <Select value={provincia} onValueChange={setProvincia}>
              <SelectTrigger>
                <SelectValue placeholder="Provincia" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas las provincias</SelectItem>
                {provincias.map((p) => (
                  <SelectItem key={p} value={p}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={rubro} onValueChange={setRubro}>
              <SelectTrigger>
                <SelectValue placeholder="Rubro" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los rubros</SelectItem>
                {rubros.map((r) => (
                  <SelectItem key={r} value={r}>{r}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={estado} onValueChange={setEstado}>
              <SelectTrigger>
                <SelectValue placeholder="Estado" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los estados</SelectItem>
                <SelectItem value="nuevo">Nuevo</SelectItem>
                <SelectItem value="contactado">Contactado</SelectItem>
                <SelectItem value="interesado">Interesado</SelectItem>
                <SelectItem value="cliente">Cliente</SelectItem>
                <SelectItem value="descartado">Descartado</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-wrap items-center gap-4 mt-3">
            <div className="flex items-center gap-2">
              <Switch id="solo-email" checked={soloEmail} onCheckedChange={setSoloEmail} />
              <Label htmlFor="solo-email" className="text-sm cursor-pointer">Solo con email</Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch id="solo-tel" checked={soloTelefono} onCheckedChange={setSoloTelefono} />
              <Label htmlFor="solo-tel" className="text-sm cursor-pointer">Solo con teléfono</Label>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="w-6 h-6 animate-spin opacity-50" style={{ color: '#6B4F3A' }} />
            </div>
          ) : leads.length === 0 ? (
            <div className="flex items-center justify-center h-48" style={{ color: '#6B4F3A' }}>
              No se encontraron leads
            </div>
          ) : (
            <>
              {/* Mobile: card list */}
              <div className="sm:hidden divide-y">
                {leads.map((lead) => (
                  <div
                    key={lead.id}
                    className="flex items-start justify-between gap-3 px-4 py-3 cursor-pointer active:bg-slate-50"
                    onClick={() => router.push(`/leads/${lead.id}`)}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-sm truncate" style={{ color: '#4A3728' }}>{lead.empresa}</p>
                      <p className="text-xs mt-0.5 truncate" style={{ color: '#6B4F3A' }}>
                        {[lead.ciudad, lead.provincia].filter(Boolean).join(', ') || '—'}
                      </p>
                      {lead.telefono && (
                        <p className="text-xs text-slate-500 mt-0.5">{lead.telefono}</p>
                      )}
                    </div>
                    <div className="flex flex-col items-end gap-1.5 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                      <ScoreBadge score={lead.score} />
                      <Select
                        value={lead.estado ?? 'nuevo'}
                        onValueChange={async (newEstado) => {
                          await updateLead(lead.id, { estado: newEstado })
                          setLeads((prev) => prev.map((l) => l.id === lead.id ? { ...l, estado: newEstado } : l))
                        }}
                      >
                        <SelectTrigger className="h-7 text-xs w-28 border-0 shadow-none p-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="nuevo">Nuevo</SelectItem>
                          <SelectItem value="contactado">Contactado</SelectItem>
                          <SelectItem value="interesado">Interesado</SelectItem>
                          <SelectItem value="cliente">Cliente</SelectItem>
                          <SelectItem value="descartado">Descartado</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                ))}
              </div>

              {/* Desktop: full table */}
              <div className="hidden sm:block overflow-x-auto">
              <Table className="min-w-[750px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Empresa</TableHead>
                    <TableHead>Ciudad / Provincia</TableHead>
                    <TableHead>Teléfono</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Score</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead>Rubro</TableHead>
                    <TableHead className="w-20">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {leads.map((lead) => (
                    <TableRow
                      key={lead.id}
                      className="cursor-pointer"
                      onClick={() => router.push(`/leads/${lead.id}`)}
                    >
                      <TableCell className="font-medium" style={{ color: '#4A3728' }}>{lead.empresa}</TableCell>
                      <TableCell style={{ color: '#6B4F3A' }}>
                        {[lead.ciudad, lead.provincia].filter(Boolean).join(', ') || '—'}
                      </TableCell>
                      <TableCell style={{ color: '#6B4F3A' }}>{lead.telefono || '—'}</TableCell>
                      <TableCell style={{ color: '#6B4F3A' }}>
                        {lead.email ? (
                          <span className="text-blue-600">{lead.email}</span>
                        ) : '—'}
                      </TableCell>
                      <TableCell><ScoreBadge score={lead.score} /></TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Select
                          value={lead.estado ?? 'nuevo'}
                          onValueChange={async (newEstado) => {
                            await updateLead(lead.id, { estado: newEstado })
                            setLeads((prev) => prev.map((l) => l.id === lead.id ? { ...l, estado: newEstado } : l))
                          }}
                        >
                          <SelectTrigger className="h-7 text-xs w-32 border-0 shadow-none p-1">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="nuevo">Nuevo</SelectItem>
                            <SelectItem value="contactado">Contactado</SelectItem>
                            <SelectItem value="interesado">Interesado</SelectItem>
                            <SelectItem value="cliente">Cliente</SelectItem>
                            <SelectItem value="descartado">Descartado</SelectItem>
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell className="text-slate-600 capitalize">{lead.rubro || '—'}</TableCell>
                      <TableCell>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={(e) => {
                            e.stopPropagation()
                            router.push(`/leads/${lead.id}`)
                          }}
                        >
                          Ver
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-500">
            Página {page} de {pages} ({total.toLocaleString('es-AR')} resultados)
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              <ChevronLeft className="w-4 h-4" />
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              disabled={page >= pages}
            >
              Siguiente
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

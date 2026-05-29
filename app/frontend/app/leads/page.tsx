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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { getLeads, getLeadStats, getLeadRubros, getApiUrl, updateLead, quickSendLeads, generateCampaignText } from '@/lib/api'
import { Search, Download, ChevronLeft, ChevronRight, Loader2, Mail, MessageSquare, FileDown, Sparkles, Upload } from 'lucide-react'

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

interface WaLink {
  empresa: string
  telefono: string
  url: string
}

function ScoreBadge({ score }: { score?: number }) {
  if (score === undefined || score === null) return <span className="text-slate-400">—</span>
  if (score >= 7) return <Badge variant="success">{score}</Badge>
  if (score >= 4) return <Badge variant="warning">{score}</Badge>
  return <Badge variant="danger">{score}</Badge>
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

  // Multi-select & contact
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [showContactDialog, setShowContactDialog] = useState(false)
  const [contactType, setContactType] = useState<'email' | 'whatsapp' | 'catalogo'>('email')
  const [emailSubject, setEmailSubject] = useState('')
  const [emailBody, setEmailBody] = useState('')
  const [waMessage, setWaMessage] = useState('')
  const [waLinks, setWaLinks] = useState<WaLink[] | null>(null)
  const [sending, setSending] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [sendResult, setSendResult] = useState('')
  const [aiError, setAiError] = useState('')

  // CSV Import
  const [showImportDialog, setShowImportDialog] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{ inserted: number; skipped: number } | null>(null)

  const fetchLeads = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number | boolean> = { page, limit: 50 }
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

  useEffect(() => { fetchLeads() }, [fetchLeads])

  useEffect(() => {
    getLeadStats().then((s) => {
      setProvincias((s.por_provincia ?? []).map((p: { provincia: string }) => p.provincia))
    }).catch(() => {})
    getLeadRubros().then((r) => setRubros(r.rubros ?? [])).catch(() => {})
  }, [])

  useEffect(() => { setPage(1) }, [search, provincia, rubro, estado, soloEmail, soloTelefono])

  // Reset selection when page/filters change
  useEffect(() => { setSelectedIds(new Set()) }, [page, search, provincia, rubro, estado])

  const toggleSelect = (id: number, e: React.MouseEvent) => {
    e.stopPropagation()
    setSelectedIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    setSelectedIds(selectedIds.size === leads.length ? new Set() : new Set(leads.map((l) => l.id)))
  }

  const openContactDialog = (type: 'email' | 'whatsapp' | 'catalogo') => {
    setContactType(type)
    setWaLinks(null)
    setSendResult('')
    if (type === 'catalogo') {
      const catalogUrl = 'https://kairos.polkorp.com/public/catalog'
      setEmailSubject('Catálogo de Productos Kairos')
      setEmailBody(`Hola, te compartimos nuestro catálogo de productos:\n${catalogUrl}\n\nQuedamos a tu disposición para cualquier consulta.`)
      setWaMessage(`Hola! Te compartimos nuestro catálogo de productos 🌿\n${catalogUrl}`)
    } else if (type === 'email') {
      setEmailSubject('')
      setEmailBody('')
    } else {
      setWaMessage('')
    }
    setShowContactDialog(true)
  }

  const handleSendEmail = async () => {
    setSending(true)
    try {
      const result = await quickSendLeads({
        lead_ids: Array.from(selectedIds),
        tipo: 'email',
        asunto: emailSubject,
        cuerpo: emailBody,
      })
      const extra = result.sin_email > 0 ? ` (${result.sin_email} sin email)` : ''
      setSendResult(`✓ ${result.queued} email${result.queued !== 1 ? 's' : ''} enviado${result.queued !== 1 ? 's' : ''}${extra}`)
    } catch {
      setSendResult('Error al enviar. Verificá la configuración de Brevo.')
    } finally {
      setSending(false)
    }
  }

  const handleGetWaLinks = async () => {
    setSending(true)
    try {
      const result = await quickSendLeads({
        lead_ids: Array.from(selectedIds),
        tipo: 'whatsapp',
        cuerpo: contactType === 'catalogo' ? waMessage : waMessage,
      })
      setWaLinks(result.links ?? [])
    } catch {
      setWaLinks([])
    } finally {
      setSending(false)
    }
  }

  const handleGenerateAI = async () => {
    setGenerating(true)
    setAiError('')
    try {
      const segDesc = [
        rubro !== 'all' ? rubro : 'tiendas holísticas y de sahumerios',
        provincia !== 'all' ? `en ${provincia}` : 'en Argentina',
      ].join(' ')
      const result = await generateCampaignText({
        tipo: 'email',
        segmento_desc: segDesc,
      })
      if (result.asunto) setEmailSubject(result.asunto)
      if (result.cuerpo) setEmailBody(result.cuerpo)
    } catch (err) {
      setAiError(err instanceof Error ? err.message : 'Error al generar. Verificá que ANTHROPIC_API_KEY esté configurada en Render.')
    } finally {
      setGenerating(false)
    }
  }

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

  const handleImport = async () => {
    if (!importFile) return
    setImporting(true)
    try {
      const formData = new FormData()
      formData.append('file', importFile)
      const res = await fetch(`${getApiUrl('/leads/import')}`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error(await res.text())
      const result = await res.json()
      setImportResult(result)
      fetchLeads()
    } catch {
      setImportResult({ inserted: 0, skipped: -1 })
    } finally {
      setImporting(false)
    }
  }

  const allSelected = leads.length > 0 && selectedIds.size === leads.length

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: '#4A3728' }}>Leads</h1>
          <p className="mt-1" style={{ color: '#6B4F3A' }}>{total.toLocaleString('es-AR')} leads en total</p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={() => setShowImportDialog(true)} variant="outline" className="gap-2">
            <Upload className="w-4 h-4" />
            Importar CSV
          </Button>
          <Button onClick={handleExport} variant="outline" className="gap-2">
            <Download className="w-4 h-4" />
            Exportar CSV
          </Button>
        </div>
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
              <SelectTrigger><SelectValue placeholder="Provincia" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas las provincias</SelectItem>
                {provincias.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
              </SelectContent>
            </Select>

            <Select value={rubro} onValueChange={setRubro}>
              <SelectTrigger><SelectValue placeholder="Rubro" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los rubros</SelectItem>
                {rubros.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
              </SelectContent>
            </Select>

            <Select value={estado} onValueChange={setEstado}>
              <SelectTrigger><SelectValue placeholder="Estado" /></SelectTrigger>
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
                    className={`flex items-start gap-3 px-4 py-3 cursor-pointer active:bg-slate-50 ${selectedIds.has(lead.id) ? 'bg-amber-50' : ''}`}
                    onClick={() => router.push(`/leads/${lead.id}`)}
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(lead.id)}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => { e.stopPropagation(); toggleSelect(lead.id, e as unknown as React.MouseEvent) }}
                      className="mt-1 w-4 h-4 cursor-pointer flex-shrink-0 accent-amber-600"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-sm truncate" style={{ color: '#4A3728' }}>{lead.empresa}</p>
                      <p className="text-xs mt-0.5 truncate" style={{ color: '#6B4F3A' }}>
                        {[lead.ciudad, lead.provincia].filter(Boolean).join(', ') || '—'}
                      </p>
                      {lead.telefono && <p className="text-xs text-slate-500 mt-0.5">{lead.telefono}</p>}
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
                <Table className="min-w-[800px]">
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10">
                        <input
                          type="checkbox"
                          checked={allSelected}
                          onChange={toggleSelectAll}
                          className="w-4 h-4 cursor-pointer accent-amber-600"
                        />
                      </TableHead>
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
                        className={`cursor-pointer ${selectedIds.has(lead.id) ? 'bg-amber-50' : ''}`}
                        onClick={() => router.push(`/leads/${lead.id}`)}
                      >
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={selectedIds.has(lead.id)}
                            onChange={(e) => toggleSelect(lead.id, e as unknown as React.MouseEvent)}
                            className="w-4 h-4 cursor-pointer accent-amber-600"
                          />
                        </TableCell>
                        <TableCell className="font-medium" style={{ color: '#4A3728' }}>{lead.empresa}</TableCell>
                        <TableCell style={{ color: '#6B4F3A' }}>
                          {[lead.ciudad, lead.provincia].filter(Boolean).join(', ') || '—'}
                        </TableCell>
                        <TableCell style={{ color: '#6B4F3A' }}>{lead.telefono || '—'}</TableCell>
                        <TableCell style={{ color: '#6B4F3A' }}>
                          {lead.email ? <span className="text-blue-600">{lead.email}</span> : '—'}
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
                            onClick={(e) => { e.stopPropagation(); router.push(`/leads/${lead.id}`) }}
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
            <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>
              <ChevronLeft className="w-4 h-4" />
              Anterior
            </Button>
            <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.min(pages, p + 1))} disabled={page >= pages}>
              Siguiente
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Floating action bar */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-white shadow-2xl border border-slate-200 rounded-2xl px-5 py-3 flex flex-wrap items-center gap-3">
          <span className="text-sm font-semibold" style={{ color: '#4A3728' }}>
            {selectedIds.size} seleccionado{selectedIds.size !== 1 ? 's' : ''}
          </span>
          <div className="w-px h-5 bg-slate-200" />
          <Button size="sm" className="gap-1.5 h-8" onClick={() => openContactDialog('email')}>
            <Mail className="w-3.5 h-3.5" />
            Email
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="gap-1.5 h-8 text-green-700 border-green-200 hover:bg-green-50"
            onClick={() => openContactDialog('whatsapp')}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            WhatsApp
          </Button>
          <Button size="sm" variant="outline" className="gap-1.5 h-8" onClick={() => openContactDialog('catalogo')}>
            <FileDown className="w-3.5 h-3.5" />
            Catálogo
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-slate-400 h-8 px-2"
            onClick={() => setSelectedIds(new Set())}
          >
            ✕
          </Button>
        </div>
      )}

      {/* Contact dialog */}
      <Dialog
        open={showContactDialog}
        onOpenChange={(o) => {
          setShowContactDialog(o)
          if (!o) { setWaLinks(null); setSendResult('') }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {contactType === 'whatsapp'
                ? <MessageSquare className="w-5 h-5 text-green-600" />
                : <Mail className="w-5 h-5" style={{ color: '#C9A040' }} />}
              {contactType === 'email' ? 'Enviar Email' : contactType === 'whatsapp' ? 'Enviar WhatsApp' : 'Enviar Catálogo'}
              <span className="text-sm font-normal text-slate-500 ml-1">— {selectedIds.size} leads</span>
            </DialogTitle>
          </DialogHeader>

          {sendResult ? (
            <div className="py-6 text-center text-sm font-medium text-green-700">{sendResult}</div>
          ) : (
            <div className="space-y-3 py-2">
              {(contactType === 'email' || contactType === 'catalogo') && (
                <>
                  {contactType === 'email' && (
                    <div className="space-y-1">
                      <Button
                        variant="outline"
                        size="sm"
                        className="gap-2 w-full border-dashed"
                        onClick={handleGenerateAI}
                        disabled={generating}
                      >
                        {generating
                          ? <Loader2 className="w-4 h-4 animate-spin" />
                          : <Sparkles className="w-4 h-4 text-amber-500" />}
                        {generating ? 'Generando con IA...' : 'Generar con IA en español'}
                      </Button>
                      {aiError && (
                        <p className="text-xs text-red-600">{aiError}</p>
                      )}
                    </div>
                  )}
                  <div className="space-y-1.5">
                    <Label>Asunto</Label>
                    <Input value={emailSubject} onChange={(e) => setEmailSubject(e.target.value)} placeholder="Asunto del email" />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Mensaje</Label>
                    <Textarea value={emailBody} onChange={(e) => setEmailBody(e.target.value)} rows={5} placeholder="Escribe tu mensaje..." />
                  </div>
                  <p className="text-xs text-slate-400">
                    {contactType === 'catalogo'
                      ? 'El link al catálogo PDF está incluido en el mensaje.'
                      : 'Usá {empresa} para personalizar con el nombre de cada lead.'}
                  </p>
                </>
              )}

              {contactType === 'whatsapp' && !waLinks && (
                <div className="space-y-1.5">
                  <Label>Mensaje</Label>
                  <Textarea
                    value={waMessage}
                    onChange={(e) => setWaMessage(e.target.value)}
                    rows={4}
                    placeholder="Escribe tu mensaje de WhatsApp..."
                  />
                  <p className="text-xs text-slate-400">Se generarán links wa.me para cada lead con teléfono.</p>
                </div>
              )}

              {contactType === 'whatsapp' && waLinks && (
                <div className="space-y-2">
                  <p className="text-sm font-medium text-slate-600">
                    {waLinks.length} link{waLinks.length !== 1 ? 's' : ''} generado{waLinks.length !== 1 ? 's' : ''} — hacé click para abrir cada chat:
                  </p>
                  <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                    {waLinks.length === 0 ? (
                      <p className="text-sm text-slate-500 text-center py-4">Ningún lead seleccionado tiene teléfono registrado.</p>
                    ) : waLinks.map((link, i) => (
                      <a
                        key={i}
                        href={link.url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center justify-between p-2.5 rounded-lg border border-green-200 bg-green-50 hover:bg-green-100 transition-colors"
                      >
                        <span className="text-sm font-medium text-slate-800">{link.empresa}</span>
                        <span className="text-xs text-slate-500">{link.telefono}</span>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowContactDialog(false)}>
              {sendResult ? 'Cerrar' : 'Cancelar'}
            </Button>
            {!sendResult && (
              <>
                {(contactType === 'email' || contactType === 'catalogo') && (
                  <Button onClick={handleSendEmail} disabled={!emailSubject || !emailBody || sending}>
                    {sending ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Mail className="w-4 h-4 mr-2" />}
                    Enviar
                  </Button>
                )}
                {contactType === 'whatsapp' && !waLinks && (
                  <Button
                    onClick={handleGetWaLinks}
                    disabled={!waMessage || sending}
                    className="bg-green-600 hover:bg-green-700"
                  >
                    {sending ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <MessageSquare className="w-4 h-4 mr-2" />}
                    Generar Links
                  </Button>
                )}
                {contactType === 'whatsapp' && waLinks && waLinks.length > 0 && (
                  <Button variant="outline" onClick={() => setWaLinks(null)}>
                    Regenerar
                  </Button>
                )}
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import CSV dialog */}
      <Dialog open={showImportDialog} onOpenChange={(o) => { setShowImportDialog(o); if (!o) { setImportFile(null); setImportResult(null) } }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Importar Leads desde CSV</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {importResult ? (
              <div className="text-center py-4">
                <p className="text-lg font-bold text-green-700">✓ {importResult.inserted} leads importados</p>
                <p className="text-sm text-slate-500">{importResult.skipped} omitidos (duplicados o sin nombre)</p>
              </div>
            ) : (
              <>
                <div className="space-y-1.5">
                  <Label>Archivo CSV</Label>
                  <Input type="file" accept=".csv" onChange={(e) => setImportFile(e.target.files?.[0] ?? null)} />
                </div>
                <div className="text-xs text-slate-500 space-y-1">
                  <p className="font-medium">Columnas reconocidas:</p>
                  <p>empresa / nombre, telefono, email, ciudad, provincia, rubro, website</p>
                  <p>La primera fila debe ser el encabezado. Acepta CSV de Excel (UTF-8 o con BOM).</p>
                </div>
              </>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowImportDialog(false)}>
              {importResult ? 'Cerrar' : 'Cancelar'}
            </Button>
            {!importResult && (
              <Button onClick={handleImport} disabled={!importFile || importing}>
                {importing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                Importar
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

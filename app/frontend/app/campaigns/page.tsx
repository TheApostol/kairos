'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getCampaigns, getCampaignStats, duplicateCampaign, getFollowupWhatsappLinks, processFollowups, sendReengagement } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
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
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Megaphone, Mail, TrendingUp, Users, Plus, Loader2, Copy, MessageCircle, ExternalLink, RefreshCw, UserCheck } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

interface Campaign {
  id: number
  nombre: string
  tipo: string
  estado: string
  enviados?: number
  abiertos?: number
  clicks?: number
  created_at?: string
}

interface CampaignStats {
  total: number
  emails_enviados: number
  tasa_apertura_promedio: number
  conversiones: number
}

function EstadoBadge({ estado }: { estado: string }) {
  const map: Record<string, 'success' | 'info' | 'warning' | 'gray' | 'secondary'> = {
    enviado: 'success',
    activo: 'success',
    borrador: 'gray',
    programado: 'info',
    pausado: 'warning',
    cancelado: 'gray',
  }
  return <Badge variant={map[estado] ?? 'secondary'} className="capitalize">{estado}</Badge>
}

function TipoBadge({ tipo }: { tipo: string }) {
  return (
    <Badge variant={tipo === 'email' ? 'info' : 'success'} className="capitalize">
      {tipo}
    </Badge>
  )
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '—'
  try {
    return format(new Date(dateStr), "d MMM yyyy", { locale: es })
  } catch {
    return dateStr
  }
}

function pct(value?: number, total?: number) {
  if (!value || !total || total === 0) return '—'
  return `${((value / total) * 100).toFixed(1)}%`
}

interface WaLink {
  empresa: string
  telefono: string
  url: string
}

export default function CampaignsPage() {
  const router = useRouter()
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [stats, setStats] = useState<CampaignStats | null>(null)
  const [loading, setLoading] = useState(true)

  // Seguimiento WA
  const [waDialogOpen, setWaDialogOpen] = useState(false)
  const [waLinks, setWaLinks] = useState<WaLink[]>([])
  const [waLoading, setWaLoading] = useState(false)
  const [waDias, setWaDias] = useState('3')

  // Action states
  const [processingFollowups, setProcessingFollowups] = useState(false)
  const [sendingReengagement, setSendingReengagement] = useState(false)
  const [actionMsg, setActionMsg] = useState('')

  useEffect(() => {
    Promise.all([getCampaigns(), getCampaignStats()])
      .then(([c, s]) => {
        setCampaigns(c.items ?? c ?? [])
        setStats(s)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleDuplicate = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await duplicateCampaign(id)
      const updated = await getCampaigns()
      setCampaigns(updated.items ?? updated ?? [])
    } catch {
      // silently ignore
    }
  }

  const loadWaLinks = async (dias: string) => {
    setWaLoading(true)
    try {
      const res = await getFollowupWhatsappLinks(Number(dias))
      setWaLinks(res?.links ?? [])
    } catch {
      setWaLinks([])
    } finally {
      setWaLoading(false)
    }
  }

  const handleOpenWaFollowup = () => {
    setWaDialogOpen(true)
    loadWaLinks(waDias)
  }

  const handleWaDiasChange = (val: string) => {
    setWaDias(val)
    loadWaLinks(val)
  }

  const handleOpenAll = () => {
    waLinks.forEach((link) => window.open(link.url, '_blank', 'noopener,noreferrer'))
  }

  const handleCopyAll = async () => {
    const text = waLinks.map((l) => `${l.empresa}: ${l.url}`).join('\n')
    try {
      await navigator.clipboard.writeText(text)
      setActionMsg('Links copiados al portapapeles')
      setTimeout(() => setActionMsg(''), 2500)
    } catch {
      // clipboard not available
    }
  }

  const handleProcessFollowups = async () => {
    setProcessingFollowups(true)
    setActionMsg('')
    try {
      const res = await processFollowups()
      setActionMsg(res?.message || 'Seguimientos procesados')
    } catch {
      setActionMsg('Error al procesar seguimientos')
    } finally {
      setProcessingFollowups(false)
      setTimeout(() => setActionMsg(''), 4000)
    }
  }

  const handleSendReengagement = async () => {
    if (!confirm('¿Enviar emails de reactivación a clientes sin pedidos en los últimos 30 días?')) return
    setSendingReengagement(true)
    setActionMsg('')
    try {
      const res = await sendReengagement(30)
      setActionMsg(res?.message || `${res?.queued ?? 0} emails encolados`)
    } catch {
      setActionMsg('Error al enviar reactivación')
    } finally {
      setSendingReengagement(false)
      setTimeout(() => setActionMsg(''), 4000)
    }
  }

  const statCards = [
    {
      title: 'Total Campañas',
      value: stats?.total?.toString() ?? '—',
      icon: Megaphone,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
    },
    {
      title: 'Emails Enviados',
      value: stats?.emails_enviados?.toLocaleString('es-AR') ?? '—',
      icon: Mail,
      color: 'text-emerald-600',
      bg: 'bg-emerald-50',
    },
    {
      title: 'Tasa Apertura Prom.',
      value: stats?.tasa_apertura_promedio !== undefined
        ? `${stats.tasa_apertura_promedio.toFixed(1)}%`
        : '—',
      icon: TrendingUp,
      color: 'text-orange-600',
      bg: 'bg-orange-50',
    },
    {
      title: 'Conversiones',
      value: stats?.conversiones?.toLocaleString('es-AR') ?? '—',
      icon: Users,
      color: 'text-violet-600',
      bg: 'bg-violet-50',
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Campañas</h1>
          <p className="text-slate-500 mt-1">Gestión de campañas de email y WhatsApp</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleProcessFollowups}
            disabled={processingFollowups}
            className="gap-2 border-blue-400 text-blue-700 hover:bg-blue-50"
          >
            {processingFollowups
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <RefreshCw className="w-4 h-4" />}
            Enviar seguimientos
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleSendReengagement}
            disabled={sendingReengagement}
            className="gap-2 border-violet-400 text-violet-700 hover:bg-violet-50"
          >
            {sendingReengagement
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <UserCheck className="w-4 h-4" />}
            Reactivar clientes
          </Button>
          <Button
            variant="outline"
            onClick={handleOpenWaFollowup}
            className="gap-2 border-green-600 text-green-700 hover:bg-green-50"
          >
            <MessageCircle className="w-4 h-4" />
            Seguimiento WA
          </Button>
          <Button onClick={() => router.push('/campaigns/new')} className="gap-2">
            <Plus className="w-4 h-4" />
            Nueva Campaña
          </Button>
        </div>
      </div>

      {actionMsg && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm px-4 py-2 rounded-lg">
          {actionMsg}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map(({ title, value, icon: Icon, color, bg }) => (
          <Card key={title}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-500 font-medium">{title}</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
                </div>
                <div className={`${bg} p-3 rounded-lg`}>
                  <Icon className={`w-6 h-6 ${color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            </div>
          ) : campaigns.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-slate-400 gap-3">
              <Megaphone className="w-10 h-10 opacity-40" />
              <p>No hay campañas todavía</p>
              <Button onClick={() => router.push('/campaigns/new')} size="sm">
                Crear primera campaña
              </Button>
            </div>
          ) : (
            <>
              {/* Mobile: card list */}
              <div className="sm:hidden divide-y">
                {campaigns.map((c) => (
                  <div
                    key={c.id}
                    className="flex items-start justify-between gap-3 px-4 py-3 cursor-pointer active:bg-slate-50"
                    onClick={() => router.push(`/campaigns/${c.id}`)}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="font-semibold text-sm truncate text-slate-900">{c.nombre}</p>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 px-1.5 text-xs text-slate-400 flex-shrink-0"
                          onClick={(e) => handleDuplicate(c.id, e)}
                        >
                          <Copy className="w-3 h-3 mr-1" />
                          Duplicar
                        </Button>
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">{formatDate(c.created_at)}</p>
                      <div className="flex items-center gap-2 mt-1.5">
                        <TipoBadge tipo={c.tipo} />
                        <EstadoBadge estado={c.estado} />
                      </div>
                    </div>
                    <div className="flex-shrink-0 text-right">
                      {c.enviados ? (
                        <p className="text-xs text-slate-500">{c.enviados.toLocaleString('es-AR')} env.</p>
                      ) : null}
                      {pct(c.abiertos, c.enviados) !== '—' && (
                        <p className="text-xs text-emerald-700 font-medium">{pct(c.abiertos, c.enviados)} apert.</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Desktop: full table */}
              <div className="hidden sm:block overflow-x-auto">
              <Table className="min-w-[680px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Nombre</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead>Enviados</TableHead>
                    <TableHead>Abiertos %</TableHead>
                    <TableHead>Clicks %</TableHead>
                    <TableHead>Fecha</TableHead>
                    <TableHead className="w-20">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {campaigns.map((c) => (
                    <TableRow
                      key={c.id}
                      className="cursor-pointer"
                      onClick={() => router.push(`/campaigns/${c.id}`)}
                    >
                      <TableCell className="font-medium text-slate-900">{c.nombre}</TableCell>
                      <TableCell><TipoBadge tipo={c.tipo} /></TableCell>
                      <TableCell><EstadoBadge estado={c.estado} /></TableCell>
                      <TableCell>{c.enviados?.toLocaleString('es-AR') ?? '—'}</TableCell>
                      <TableCell>{pct(c.abiertos, c.enviados)}</TableCell>
                      <TableCell>{pct(c.clicks, c.enviados)}</TableCell>
                      <TableCell className="text-slate-500">{formatDate(c.created_at)}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={(e) => {
                              e.stopPropagation()
                              router.push(`/campaigns/${c.id}`)
                            }}
                          >
                            Ver
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-slate-400 hover:text-slate-700"
                            onClick={(e) => handleDuplicate(c.id, e)}
                          >
                            <Copy className="w-3.5 h-3.5" />
                          </Button>
                        </div>
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

      {/* Seguimiento WA Dialog */}
      <Dialog open={waDialogOpen} onOpenChange={setWaDialogOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-green-700">
              <MessageCircle className="w-5 h-5" />
              Seguimiento por WhatsApp
            </DialogTitle>
          </DialogHeader>

          {/* Controls */}
          <div className="flex items-center gap-3 pb-3 border-b flex-shrink-0">
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-600">Sin respuesta hace más de</span>
              <Select value={waDias} onValueChange={handleWaDiasChange}>
                <SelectTrigger className="w-20 h-8">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1 día</SelectItem>
                  <SelectItem value="3">3 días</SelectItem>
                  <SelectItem value="7">7 días</SelectItem>
                  <SelectItem value="14">14 días</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {waLinks.length > 0 && (
              <div className="ml-auto flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={handleCopyAll}
                >
                  Copiar todos
                </Button>
                <Button
                  size="sm"
                  className="h-7 text-xs bg-green-600 hover:bg-green-700"
                  onClick={handleOpenAll}
                >
                  Abrir todos
                </Button>
              </div>
            )}
          </div>

          <div className="overflow-y-auto flex-1 mt-2">
            {waLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
              </div>
            ) : waLinks.length === 0 ? (
              <div className="text-center py-8 text-slate-500">
                <MessageCircle className="w-10 h-10 mx-auto mb-3 opacity-30" />
                <p className="font-medium">Sin leads pendientes de seguimiento</p>
                <p className="text-sm text-slate-400 mt-1">
                  No hay leads con más de {waDias} día{Number(waDias) !== 1 ? 's' : ''} sin respuesta
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-sm text-slate-500 mb-3">
                  {waLinks.length} leads — emails enviados hace más de {waDias} días sin respuesta
                </p>
                {waLinks.map((link, i) => (
                  <a
                    key={i}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between p-3 rounded-lg bg-green-50 hover:bg-green-100 transition-colors border border-green-200 group"
                  >
                    <div>
                      <p className="text-sm font-semibold text-green-900">{link.empresa || 'Sin nombre'}</p>
                      {link.telefono && (
                        <p className="text-xs text-green-700 mt-0.5">{link.telefono}</p>
                      )}
                    </div>
                    <ExternalLink className="w-4 h-4 text-green-600 opacity-60 group-hover:opacity-100" />
                  </a>
                ))}
              </div>
            )}
          </div>

          {actionMsg && (
            <p className="text-xs text-emerald-700 text-center pt-2 flex-shrink-0">{actionMsg}</p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

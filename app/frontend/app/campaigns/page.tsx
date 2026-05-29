'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getCampaigns, getCampaignStats } from '@/lib/api'
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
import { Megaphone, Mail, TrendingUp, Users, Plus, Loader2 } from 'lucide-react'
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

export default function CampaignsPage() {
  const router = useRouter()
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [stats, setStats] = useState<CampaignStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getCampaigns(), getCampaignStats()])
      .then(([c, s]) => {
        setCampaigns(c.items ?? c ?? [])
        setStats(s)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

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
        <Button onClick={() => router.push('/campaigns/new')} className="gap-2">
          <Plus className="w-4 h-4" />
          Nueva Campaña
        </Button>
      </div>

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
                      <p className="font-semibold text-sm truncate text-slate-900">{c.nombre}</p>
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
    </div>
  )
}

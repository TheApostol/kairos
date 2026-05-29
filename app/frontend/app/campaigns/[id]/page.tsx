'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { getCampaign } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ArrowLeft, Loader2, Mail, MousePointer, Reply, TrendingUp, Send } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

interface CampaignSend {
  id: number
  empresa?: string
  email?: string
  estado: string
  abierto?: boolean
  click?: boolean
  respondido?: boolean
  enviado_at?: string
}

interface Campaign {
  id: number
  nombre: string
  tipo: string
  estado: string
  asunto?: string
  cuerpo?: string
  enviados?: number
  abiertos?: number
  clicks?: number
  respondidos?: number
  convertidos?: number
  created_at?: string
  sends?: CampaignSend[]
}

function pct(value?: number, total?: number) {
  if (value === undefined || !total || total === 0) return 0
  return (value / total) * 100
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '—'
  try {
    return format(new Date(dateStr), "d MMM yyyy, HH:mm", { locale: es })
  } catch {
    return dateStr
  }
}

function SendEstadoBadge({ estado }: { estado: string }) {
  const variants: Record<string, 'success' | 'warning' | 'gray' | 'secondary'> = {
    enviado: 'success',
    abierto: 'info' as 'secondary',
    pendiente: 'warning',
    fallido: 'gray',
    rebotado: 'gray',
  }
  return <Badge variant={variants[estado] ?? 'secondary'} className="capitalize">{estado}</Badge>
}

export default function CampaignDetailPage() {
  const params = useParams()
  const router = useRouter()
  const id = params.id as string
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getCampaign(id)
      .then(setCampaign)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
      </div>
    )
  }

  if (!campaign) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500">Campaña no encontrada</p>
        <Button variant="ghost" onClick={() => router.push('/campaigns')} className="mt-4">
          Volver
        </Button>
      </div>
    )
  }

  const total = campaign.enviados ?? 0
  const openPct = pct(campaign.abiertos, total)
  const clickPct = pct(campaign.clicks, total)
  const replyPct = pct(campaign.respondidos, total)
  const convPct = pct(campaign.convertidos, total)

  const metrics = [
    {
      label: 'Enviados',
      value: total.toLocaleString('es-AR'),
      icon: Send,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
      pct: null,
    },
    {
      label: 'Abiertos',
      value: campaign.abiertos?.toLocaleString('es-AR') ?? '—',
      icon: Mail,
      color: 'text-emerald-600',
      bg: 'bg-emerald-50',
      pct: openPct,
    },
    {
      label: 'Clicks',
      value: campaign.clicks?.toLocaleString('es-AR') ?? '—',
      icon: MousePointer,
      color: 'text-orange-600',
      bg: 'bg-orange-50',
      pct: clickPct,
    },
    {
      label: 'Respondidos',
      value: campaign.respondidos?.toLocaleString('es-AR') ?? '—',
      icon: Reply,
      color: 'text-violet-600',
      bg: 'bg-violet-50',
      pct: replyPct,
    },
    {
      label: 'Convertidos',
      value: campaign.convertidos?.toLocaleString('es-AR') ?? '—',
      icon: TrendingUp,
      color: 'text-amber-600',
      bg: 'bg-amber-50',
      pct: convPct,
    },
  ]

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push('/campaigns')}>
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{campaign.nombre}</h1>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant={campaign.tipo === 'email' ? 'info' : 'success'} className="capitalize">
              {campaign.tipo}
            </Badge>
            <Badge variant="secondary" className="capitalize">{campaign.estado}</Badge>
            <span className="text-sm text-slate-500">{formatDate(campaign.created_at)}</span>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {metrics.map(({ label, value, icon: Icon, color, bg, pct: p }) => (
          <Card key={label}>
            <CardContent className="pt-4 pb-4">
              <div className={`${bg} w-8 h-8 rounded-lg flex items-center justify-center mb-2`}>
                <Icon className={`w-4 h-4 ${color}`} />
              </div>
              <p className="text-xl font-bold text-slate-900">{value}</p>
              <p className="text-xs text-slate-500">{label}</p>
              {p !== null && p !== undefined && (
                <p className={`text-xs font-medium mt-0.5 ${color}`}>{p.toFixed(1)}%</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Progress Bars */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Rendimiento de la Campaña</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {[
            { label: 'Tasa de Apertura', value: openPct, color: 'text-emerald-600' },
            { label: 'Tasa de Clicks', value: clickPct, color: 'text-orange-600' },
            { label: 'Tasa de Respuesta', value: replyPct, color: 'text-violet-600' },
            { label: 'Tasa de Conversión', value: convPct, color: 'text-amber-600' },
          ].map(({ label, value, color }) => (
            <div key={label} className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-600">{label}</span>
                <span className={`font-semibold ${color}`}>{value.toFixed(1)}%</span>
              </div>
              <Progress value={value} className="h-2" />
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Sends Table */}
      {campaign.sends && campaign.sends.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Envíos Individuales</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Empresa</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Abierto</TableHead>
                  <TableHead>Click</TableHead>
                  <TableHead>Respondido</TableHead>
                  <TableHead>Enviado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {campaign.sends.map((send) => (
                  <TableRow key={send.id}>
                    <TableCell className="font-medium">{send.empresa || '—'}</TableCell>
                    <TableCell className="text-slate-500">{send.email || '—'}</TableCell>
                    <TableCell><SendEstadoBadge estado={send.estado} /></TableCell>
                    <TableCell>
                      <span className={send.abierto ? 'text-emerald-600' : 'text-slate-400'}>
                        {send.abierto ? '✓' : '—'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={send.click ? 'text-orange-600' : 'text-slate-400'}>
                        {send.click ? '✓' : '—'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={send.respondido ? 'text-violet-600' : 'text-slate-400'}>
                        {send.respondido ? '✓' : '—'}
                      </span>
                    </TableCell>
                    <TableCell className="text-slate-500">{formatDate(send.enviado_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

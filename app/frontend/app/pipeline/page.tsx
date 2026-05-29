'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getLeads, updateLead } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Loader2, ChevronRight, ChevronLeft, X } from 'lucide-react'

interface Lead {
  id: number
  empresa: string
  ciudad?: string
  provincia?: string
  telefono?: string
  score?: number
  estado?: string
}

const ESTADOS = ['nuevo', 'contactado', 'interesado', 'cliente', 'descartado'] as const
type Estado = typeof ESTADOS[number]

const ESTADO_LABELS: Record<Estado, string> = {
  nuevo: 'Nuevo',
  contactado: 'Contactado',
  interesado: 'Interesado',
  cliente: 'Cliente',
  descartado: 'Descartado',
}

const ESTADO_COLORS: Record<Estado, string> = {
  nuevo: 'bg-slate-50 border-slate-200',
  contactado: 'bg-blue-50 border-blue-100',
  interesado: 'bg-amber-50 border-amber-100',
  cliente: 'bg-emerald-50 border-emerald-100',
  descartado: 'bg-red-50 border-red-100',
}

function ScoreBadge({ score }: { score?: number }) {
  if (score === undefined || score === null) return null
  if (score >= 7) return <Badge variant="success">{score}</Badge>
  if (score >= 4) return <Badge variant="warning">{score}</Badge>
  return <Badge variant="danger">{score}</Badge>
}

export default function PipelinePage() {
  const router = useRouter()
  const [leads, setLeads] = useState<Lead[]>([])
  const [loading, setLoading] = useState(true)
  const [moving, setMoving] = useState<number | null>(null)

  useEffect(() => {
    getLeads({ limit: 200 })
      .then((data) => {
        setLeads(data.items ?? data ?? [])
      })
      .catch(() => setLeads([]))
      .finally(() => setLoading(false))
  }, [])

  const byEstado = ESTADOS.reduce<Record<Estado, Lead[]>>((acc, e) => {
    acc[e] = leads.filter((l) => (l.estado ?? 'nuevo') === e)
    return acc
  }, { nuevo: [], contactado: [], interesado: [], cliente: [], descartado: [] })

  const moveLead = async (lead: Lead, newEstado: Estado) => {
    setMoving(lead.id)
    try {
      await updateLead(lead.id, { estado: newEstado })
      setLeads((prev) =>
        prev.map((l) => l.id === lead.id ? { ...l, estado: newEstado } : l)
      )
    } catch {
      // silent — local state unchanged on error
    } finally {
      setMoving(null)
    }
  }

  const prevEstado = (estado: Estado): Estado | null => {
    const idx = ESTADOS.indexOf(estado)
    // "descartado" has no prev in the main flow
    if (estado === 'descartado') return null
    return idx > 0 ? ESTADOS[idx - 1] : null
  }

  const nextEstado = (estado: Estado): Estado | null => {
    const idx = ESTADOS.indexOf(estado)
    // "descartado" has no next in the main flow
    if (estado === 'descartado') return null
    // "cliente" is the last main stage before descartado
    const mainStages: Estado[] = ['nuevo', 'contactado', 'interesado', 'cliente']
    const mainIdx = mainStages.indexOf(estado)
    if (mainIdx === -1) return null
    return mainIdx < mainStages.length - 1 ? mainStages[mainIdx + 1] : null
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: '#4A3728' }}>
          Pipeline de Ventas
        </h1>
        <p className="mt-1" style={{ color: '#6B4F3A' }}>
          {loading ? 'Cargando...' : `${leads.length} lead${leads.length !== 1 ? 's' : ''} en total`}
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin" style={{ color: '#C9A040' }} />
        </div>
      ) : (
        <div className="flex gap-4 items-start overflow-x-auto pb-4 lg:grid lg:grid-cols-5 lg:overflow-visible lg:pb-0">
          <style>{`.pipeline-col { min-width: 220px; flex-shrink: 0; } @media (min-width: 1024px) { .pipeline-col { min-width: unset; flex-shrink: unset; } }`}</style>
          {ESTADOS.map((estado) => {
            const colLeads = byEstado[estado]
            return (
              <div
                key={estado}
                className={`pipeline-col rounded-xl border-2 ${ESTADO_COLORS[estado]} p-3`}
              >
                {/* Column header */}
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-slate-700">
                    {ESTADO_LABELS[estado]}
                  </h3>
                  <span className="text-xs font-bold text-slate-500 bg-white/60 px-2 py-0.5 rounded-full">
                    {colLeads.length}
                  </span>
                </div>

                {/* Cards */}
                <div className="space-y-2">
                  {colLeads.length === 0 ? (
                    <div className="text-center py-8 text-slate-400 text-xs">
                      Sin leads
                    </div>
                  ) : (
                    colLeads.map((lead) => {
                      const currentEstado = (lead.estado ?? 'nuevo') as Estado
                      const prev = prevEstado(currentEstado)
                      const next = nextEstado(currentEstado)
                      const isMoving = moving === lead.id
                      return (
                        <Card
                          key={lead.id}
                          className="cursor-pointer hover:shadow-md transition-shadow bg-white"
                          onClick={() => router.push(`/leads/${lead.id}`)}
                        >
                          <CardContent className="p-3">
                            {/* Company name */}
                            <p
                              className="text-sm font-semibold leading-tight mb-1 truncate"
                              style={{ color: '#4A3728' }}
                            >
                              {lead.empresa}
                            </p>

                            {/* Location */}
                            {(lead.ciudad || lead.provincia) && (
                              <p className="text-xs text-slate-500 truncate mb-1.5">
                                {[lead.ciudad, lead.provincia].filter(Boolean).join(', ')}
                              </p>
                            )}

                            {/* Phone */}
                            {lead.telefono && (
                              <p className="text-xs text-slate-400 truncate mb-1.5">
                                {lead.telefono}
                              </p>
                            )}

                            {/* Score + action buttons */}
                            <div
                              className="flex items-center justify-between mt-2"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <ScoreBadge score={lead.score} />
                              <div className="flex items-center gap-0.5">
                                {prev && (
                                  <Button
                                    size="icon"
                                    variant="ghost"
                                    className="h-6 w-6 text-slate-400 hover:text-slate-700"
                                    disabled={isMoving}
                                    onClick={() => moveLead(lead, prev)}
                                    title={`Mover a ${ESTADO_LABELS[prev]}`}
                                  >
                                    {isMoving ? (
                                      <Loader2 className="h-3 w-3 animate-spin" />
                                    ) : (
                                      <ChevronLeft className="h-3 w-3" />
                                    )}
                                  </Button>
                                )}
                                {next && (
                                  <Button
                                    size="icon"
                                    variant="ghost"
                                    className="h-6 w-6 text-slate-400 hover:text-slate-700"
                                    disabled={isMoving}
                                    onClick={() => moveLead(lead, next)}
                                    title={`Mover a ${ESTADO_LABELS[next]}`}
                                  >
                                    {isMoving ? (
                                      <Loader2 className="h-3 w-3 animate-spin" />
                                    ) : (
                                      <ChevronRight className="h-3 w-3" />
                                    )}
                                  </Button>
                                )}
                                {estado !== 'descartado' && (
                                  <Button
                                    size="icon"
                                    variant="ghost"
                                    className="h-6 w-6 text-slate-400 hover:text-red-500"
                                    disabled={isMoving}
                                    onClick={() => moveLead(lead, 'descartado')}
                                    title="Descartar"
                                  >
                                    {isMoving ? (
                                      <Loader2 className="h-3 w-3 animate-spin" />
                                    ) : (
                                      <X className="h-3 w-3" />
                                    )}
                                  </Button>
                                )}
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      )
                    })
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

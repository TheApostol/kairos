'use client'

import { useEffect, useRef, useState } from 'react'
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

const ESTADO_COLORS: Record<Estado, { base: string; over: string }> = {
  nuevo:       { base: 'bg-slate-50 border-slate-200',   over: 'bg-slate-100 border-slate-400' },
  contactado:  { base: 'bg-blue-50 border-blue-100',     over: 'bg-blue-100 border-blue-400' },
  interesado:  { base: 'bg-amber-50 border-amber-100',   over: 'bg-amber-100 border-amber-400' },
  cliente:     { base: 'bg-emerald-50 border-emerald-100', over: 'bg-emerald-100 border-emerald-400' },
  descartado:  { base: 'bg-red-50 border-red-100',       over: 'bg-red-100 border-red-400' },
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
  const [dragOverCol, setDragOverCol] = useState<Estado | null>(null)
  const dragLeadId = useRef<number | null>(null)

  useEffect(() => {
    getLeads({ limit: 500 })
      .then((data) => setLeads(data.items ?? data ?? []))
      .catch(() => setLeads([]))
      .finally(() => setLoading(false))
  }, [])

  const byEstado = ESTADOS.reduce<Record<Estado, Lead[]>>((acc, e) => {
    acc[e] = leads.filter((l) => (l.estado ?? 'nuevo') === e)
    return acc
  }, { nuevo: [], contactado: [], interesado: [], cliente: [], descartado: [] })

  const moveLead = async (lead: Lead, newEstado: Estado) => {
    if ((lead.estado ?? 'nuevo') === newEstado) return
    setMoving(lead.id)
    // Optimistic update
    setLeads((prev) => prev.map((l) => l.id === lead.id ? { ...l, estado: newEstado } : l))
    try {
      await updateLead(lead.id, { estado: newEstado })
    } catch {
      // Revert on error
      setLeads((prev) => prev.map((l) => l.id === lead.id ? { ...l, estado: lead.estado } : l))
    } finally {
      setMoving(null)
    }
  }

  const prevEstado = (estado: Estado): Estado | null => {
    if (estado === 'descartado') return null
    const idx = ESTADOS.indexOf(estado)
    return idx > 0 ? ESTADOS[idx - 1] : null
  }

  const nextEstado = (estado: Estado): Estado | null => {
    if (estado === 'descartado') return null
    const mainStages: Estado[] = ['nuevo', 'contactado', 'interesado', 'cliente']
    const mainIdx = mainStages.indexOf(estado)
    if (mainIdx === -1) return null
    return mainIdx < mainStages.length - 1 ? mainStages[mainIdx + 1] : null
  }

  // ── Drag handlers ──────────────────────────────────────────────
  const onDragStart = (leadId: number) => {
    dragLeadId.current = leadId
  }

  const onDragOver = (e: React.DragEvent, estado: Estado) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDragOverCol(estado)
  }

  const onDragLeave = () => setDragOverCol(null)

  const onDrop = (e: React.DragEvent, targetEstado: Estado) => {
    e.preventDefault()
    setDragOverCol(null)
    const id = dragLeadId.current
    if (!id) return
    const lead = leads.find((l) => l.id === id)
    if (lead) moveLead(lead, targetEstado)
    dragLeadId.current = null
  }

  const onDragEnd = () => {
    dragLeadId.current = null
    setDragOverCol(null)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: '#4A3728' }}>
          Pipeline de Ventas
        </h1>
        <p className="mt-1 text-sm" style={{ color: '#6B4F3A' }}>
          {loading ? 'Cargando...' : `${leads.length} lead${leads.length !== 1 ? 's' : ''} en total · arrastrá las tarjetas para moverlas`}
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
            const isOver = dragOverCol === estado
            const colors = ESTADO_COLORS[estado]
            return (
              <div
                key={estado}
                className={`pipeline-col rounded-xl border-2 transition-colors p-3 ${isOver ? colors.over : colors.base}`}
                onDragOver={(e) => onDragOver(e, estado)}
                onDragLeave={onDragLeave}
                onDrop={(e) => onDrop(e, estado)}
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

                {/* Drop hint */}
                {isOver && (
                  <div className="mb-2 border-2 border-dashed border-current rounded-lg h-14 opacity-40" />
                )}

                {/* Cards */}
                <div className="space-y-2">
                  {colLeads.length === 0 && !isOver ? (
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
                          draggable
                          onDragStart={() => onDragStart(lead.id)}
                          onDragEnd={onDragEnd}
                          className="cursor-grab active:cursor-grabbing hover:shadow-md transition-shadow bg-white select-none"
                          onClick={() => router.push(`/leads/${lead.id}`)}
                        >
                          <CardContent className="p-3">
                            <p
                              className="text-sm font-semibold leading-tight mb-1 truncate"
                              style={{ color: '#4A3728' }}
                            >
                              {lead.empresa}
                            </p>

                            {(lead.ciudad || lead.provincia) && (
                              <p className="text-xs text-slate-500 truncate mb-1.5">
                                {[lead.ciudad, lead.provincia].filter(Boolean).join(', ')}
                              </p>
                            )}

                            {lead.telefono && (
                              <p className="text-xs text-slate-400 truncate mb-1.5">
                                {lead.telefono}
                              </p>
                            )}

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
                                    {isMoving ? <Loader2 className="h-3 w-3 animate-spin" /> : <ChevronLeft className="h-3 w-3" />}
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
                                    {isMoving ? <Loader2 className="h-3 w-3 animate-spin" /> : <ChevronRight className="h-3 w-3" />}
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
                                    {isMoving ? <Loader2 className="h-3 w-3 animate-spin" /> : <X className="h-3 w-3" />}
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

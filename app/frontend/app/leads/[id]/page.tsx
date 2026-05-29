'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { getLead, updateLead, createLeadNote, getOrders } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  ArrowLeft,
  Loader2,
  Phone,
  Mail,
  Globe,
  MapPin,
  Building2,
  Tag,
  MessageSquarePlus,
  ShoppingCart,
  Calendar,
  FileText,
} from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

interface Lead {
  id: number
  empresa: string
  ciudad?: string
  provincia?: string
  pais?: string
  telefono?: string
  email?: string
  website?: string
  rubro?: string
  score?: number
  estado?: string
  observaciones?: string
  fuente?: string
  created_at?: string
  updated_at?: string
  notas?: Array<{ id: number; texto: string; created_at: string }>
}

interface Order {
  id: number
  numero: string
  estado: string
  total: number
  created_at: string
}

function ScoreBadge({ score }: { score?: number }) {
  if (score === undefined || score === null) return <span className="text-slate-400">—</span>
  if (score >= 7) return <Badge variant="success">Score: {score}/10</Badge>
  if (score >= 4) return <Badge variant="warning">Score: {score}/10</Badge>
  return <Badge variant="danger">Score: {score}/10</Badge>
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

function formatDate(dateStr?: string) {
  if (!dateStr) return '—'
  try {
    return format(new Date(dateStr), "d MMM yyyy, HH:mm", { locale: es })
  } catch {
    return dateStr
  }
}

function formatCurrency(n: number) {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n)
}

export default function LeadDetailPage() {
  const params = useParams()
  const router = useRouter()
  const id = params.id as string

  const [lead, setLead] = useState<Lead | null>(null)
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [noteText, setNoteText] = useState('')
  const [addingNote, setAddingNote] = useState(false)
  const [showNoteForm, setShowNoteForm] = useState(false)

  // Editable fields
  const [estado, setEstado] = useState('')
  const [observaciones, setObservaciones] = useState('')
  const [hasChanges, setHasChanges] = useState(false)

  useEffect(() => {
    Promise.all([getLead(id), getOrders({ lead_id: id })])
      .then(([l, o]) => {
        setLead(l)
        setEstado(l.estado ?? 'nuevo')
        setObservaciones(l.observaciones ?? '')
        setOrders(o.items ?? o ?? [])
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [id])

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await updateLead(id, { estado, observaciones })
      setLead(updated)
      setHasChanges(false)
    } catch {
    } finally {
      setSaving(false)
    }
  }

  const handleAddNote = async () => {
    if (!noteText.trim()) return
    setAddingNote(true)
    try {
      await createLeadNote(id, noteText)
      const updated = await getLead(id)
      setLead(updated)
      setNoteText('')
      setShowNoteForm(false)
    } catch {
    } finally {
      setAddingNote(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
      </div>
    )
  }

  if (!lead) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500">Lead no encontrado</p>
        <Button variant="ghost" onClick={() => router.push('/leads')} className="mt-4">
          Volver a Leads
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push('/leads')}>
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900">{lead.empresa}</h1>
            <EstadoBadge estado={lead.estado} />
            <ScoreBadge score={lead.score} />
          </div>
          <p className="text-slate-500 mt-1">
            {[lead.ciudad, lead.provincia, lead.pais].filter(Boolean).join(', ') || 'Sin ubicación'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => router.push(`/orders?lead_id=${lead.id}`)} variant="outline" size="sm">
            <ShoppingCart className="w-4 h-4 mr-2" />
            Ver Pedidos
          </Button>
          <Button onClick={() => router.push(`/orders/new?lead_id=${lead.id}`)} size="sm">
            <ShoppingCart className="w-4 h-4 mr-2" />
            Crear Pedido
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Lead Info */}
        <div className="lg:col-span-1 space-y-4">
          {/* Contact Info */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
                Información de Contacto
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {lead.telefono && (
                <div className="flex items-center gap-3">
                  <Phone className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  <a href={`tel:${lead.telefono}`} className="text-sm text-blue-600 hover:underline">
                    {lead.telefono}
                  </a>
                </div>
              )}
              {lead.email && (
                <div className="flex items-center gap-3">
                  <Mail className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  <a href={`mailto:${lead.email}`} className="text-sm text-blue-600 hover:underline truncate">
                    {lead.email}
                  </a>
                </div>
              )}
              {lead.website && (
                <div className="flex items-center gap-3">
                  <Globe className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  <a
                    href={lead.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:underline truncate"
                  >
                    {lead.website}
                  </a>
                </div>
              )}
              {(lead.ciudad || lead.provincia) && (
                <div className="flex items-center gap-3">
                  <MapPin className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  <span className="text-sm text-slate-600">
                    {[lead.ciudad, lead.provincia].filter(Boolean).join(', ')}
                  </span>
                </div>
              )}
              {lead.rubro && (
                <div className="flex items-center gap-3">
                  <Building2 className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  <span className="text-sm text-slate-600 capitalize">{lead.rubro}</span>
                </div>
              )}
              {lead.fuente && (
                <div className="flex items-center gap-3">
                  <Tag className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  <span className="text-sm text-slate-600 capitalize">{lead.fuente}</span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Editable Fields */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
                Gestión
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label>Estado</Label>
                <Select
                  value={estado}
                  onValueChange={(v) => {
                    setEstado(v)
                    setHasChanges(true)
                  }}
                >
                  <SelectTrigger>
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

              <div className="space-y-1.5">
                <Label>Observaciones</Label>
                <Textarea
                  value={observaciones}
                  onChange={(e) => {
                    setObservaciones(e.target.value)
                    setHasChanges(true)
                  }}
                  placeholder="Notas internas sobre este lead..."
                  rows={4}
                />
              </div>

              <Button
                onClick={handleSave}
                disabled={!hasChanges || saving}
                className="w-full"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                Guardar Cambios
              </Button>
            </CardContent>
          </Card>

          {/* Meta */}
          <Card>
            <CardContent className="pt-4 space-y-2">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Calendar className="w-3.5 h-3.5" />
                <span>Creado: {formatDate(lead.created_at)}</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Calendar className="w-3.5 h-3.5" />
                <span>Actualizado: {formatDate(lead.updated_at)}</span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Activity & Orders */}
        <div className="lg:col-span-2 space-y-4">
          {/* Notes / Activity Timeline */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
                  Actividad y Notas
                </CardTitle>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowNoteForm(!showNoteForm)}
                >
                  <MessageSquarePlus className="w-4 h-4 mr-2" />
                  Nueva Nota
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {showNoteForm && (
                <div className="mb-4 p-4 bg-slate-50 rounded-lg space-y-3">
                  <Textarea
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    placeholder="Escribe una nota sobre este lead..."
                    rows={3}
                    className="bg-white"
                  />
                  <div className="flex gap-2 justify-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setShowNoteForm(false)
                        setNoteText('')
                      }}
                    >
                      Cancelar
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleAddNote}
                      disabled={!noteText.trim() || addingNote}
                    >
                      {addingNote ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
                      Guardar Nota
                    </Button>
                  </div>
                </div>
              )}

              {(!lead.notas || lead.notas.length === 0) ? (
                <div className="text-center py-8 text-slate-400">
                  <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">Sin notas todavía</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {[...lead.notas].reverse().map((nota) => (
                    <div key={nota.id} className="flex gap-3">
                      <div className="w-2 h-2 mt-2 rounded-full bg-blue-400 flex-shrink-0" />
                      <div className="flex-1 bg-slate-50 rounded-lg p-3">
                        <p className="text-sm text-slate-700 whitespace-pre-wrap">{nota.texto}</p>
                        <p className="text-xs text-slate-400 mt-2">{formatDate(nota.created_at)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Orders */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
                Pedidos ({orders.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {orders.length === 0 ? (
                <div className="text-center py-6 text-slate-400">
                  <ShoppingCart className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">Sin pedidos</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {orders.map((order) => (
                    <div
                      key={order.id}
                      className="flex items-center justify-between p-3 bg-slate-50 rounded-lg cursor-pointer hover:bg-slate-100"
                      onClick={() => router.push(`/orders/${order.id}`)}
                    >
                      <div>
                        <p className="text-sm font-medium text-slate-900">#{order.numero}</p>
                        <p className="text-xs text-slate-500">{formatDate(order.created_at)}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold text-slate-900">{formatCurrency(order.total)}</p>
                        <Badge variant="secondary" className="text-xs capitalize">{order.estado}</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

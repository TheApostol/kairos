'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createCampaign, generateCampaignText, getLeads } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { ArrowLeft, ArrowRight, Loader2, Sparkles, Send, CheckCircle2 } from 'lucide-react'
import { cn } from '@/lib/utils'

const STEPS = [
  { num: 1, label: 'Configurar' },
  { num: 2, label: 'Contenido' },
  { num: 3, label: 'Revisar' },
]

const PROVINCIAS = [
  'Buenos Aires', 'CABA', 'Córdoba', 'Santa Fe', 'Mendoza', 'Tucumán',
  'Entre Ríos', 'Salta', 'Chaco', 'Corrientes',
]

const RUBROS = [
  'farmacia', 'herboristería', 'dietética', 'spa', 'centro holístico',
  'cosmética', 'terapias alternativas', 'yoga', 'meditación', 'otro',
]

export default function NewCampaignPage() {
  const router = useRouter()
  const [step, setStep] = useState(1)
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [generatingAI, setGeneratingAI] = useState(false)
  const [leadsCount, setLeadsCount] = useState<number | null>(null)
  const [loadingCount, setLoadingCount] = useState(false)

  // Step 1 fields
  const [nombre, setNombre] = useState('')
  const [tipo, setTipo] = useState<'email' | 'whatsapp'>('email')
  const [segProvincia, setSegProvincia] = useState('all')
  const [segRubro, setSegRubro] = useState('all')
  const [segEstado, setSegEstado] = useState('all')
  const [segSoloEmail, setSegSoloEmail] = useState(true)

  // Step 2 fields
  const [asunto, setAsunto] = useState('')
  const [cuerpo, setCuerpo] = useState('')

  const buildSegmentParams = () => {
    const p: Record<string, string | boolean> = {}
    if (segProvincia && segProvincia !== 'all') p.provincia = segProvincia
    if (segRubro && segRubro !== 'all') p.rubro = segRubro
    if (segEstado && segEstado !== 'all') p.estado = segEstado
    if (segSoloEmail) p.con_email = true
    return p
  }

  const fetchLeadsCount = async () => {
    setLoadingCount(true)
    try {
      const params = buildSegmentParams()
      const data = await getLeads({ ...params, limit: 1 })
      setLeadsCount(data.total ?? 0)
    } catch {
      setLeadsCount(null)
    } finally {
      setLoadingCount(false)
    }
  }

  const handleGenerateAI = async () => {
    setGeneratingAI(true)
    try {
      const result = await generateCampaignText({
        nombre,
        tipo,
        segmento: {
          provincia: segProvincia !== 'all' ? segProvincia : undefined,
          rubro: segRubro !== 'all' ? segRubro : undefined,
          estado: segEstado !== 'all' ? segEstado : undefined,
        },
      })
      if (result.asunto) setAsunto(result.asunto)
      if (result.cuerpo) setCuerpo(result.cuerpo)
    } catch {
    } finally {
      setGeneratingAI(false)
    }
  }

  const handleSend = async () => {
    setSending(true)
    try {
      await createCampaign({
        nombre,
        tipo,
        asunto,
        cuerpo,
        segmento: buildSegmentParams(),
        estado: 'enviado',
      })
      setSent(true)
    } catch {
    } finally {
      setSending(false)
    }
  }

  const goToStep = (n: number) => {
    if (n === 3) fetchLeadsCount()
    setStep(n)
  }

  if (sent) {
    return (
      <div className="max-w-lg mx-auto mt-16 text-center space-y-4">
        <CheckCircle2 className="w-16 h-16 text-emerald-500 mx-auto" />
        <h2 className="text-2xl font-bold text-slate-900">Campaña enviada</h2>
        <p className="text-slate-500">Tu campaña fue creada y enviada exitosamente.</p>
        <div className="flex gap-3 justify-center">
          <Button variant="outline" onClick={() => router.push('/campaigns')}>
            Ver Campañas
          </Button>
          <Button onClick={() => {
            setSent(false)
            setStep(1)
            setNombre('')
            setAsunto('')
            setCuerpo('')
          }}>
            Nueva Campaña
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.push('/campaigns')}>
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Nueva Campaña</h1>
          <p className="text-slate-500 mt-0.5">Crea y envía una campaña a tus leads</p>
        </div>
      </div>

      {/* Stepper */}
      <div className="flex items-center gap-0">
        {STEPS.map((s, i) => (
          <div key={s.num} className="flex items-center flex-1">
            <div
              className={cn(
                'flex items-center gap-2 cursor-pointer',
                step === s.num ? 'text-blue-600' : step > s.num ? 'text-emerald-600' : 'text-slate-400'
              )}
              onClick={() => step > s.num && goToStep(s.num)}
            >
              <div
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold border-2',
                  step === s.num
                    ? 'border-blue-600 bg-blue-600 text-white'
                    : step > s.num
                    ? 'border-emerald-600 bg-emerald-600 text-white'
                    : 'border-slate-300 text-slate-400'
                )}
              >
                {step > s.num ? '✓' : s.num}
              </div>
              <span className="text-sm font-medium hidden sm:block">{s.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={cn(
                  'flex-1 h-0.5 mx-3',
                  step > s.num ? 'bg-emerald-400' : 'bg-slate-200'
                )}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step 1: Configurar */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Paso 1: Configuración</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label>Nombre de la campaña *</Label>
              <Input
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="Ej: Promo Invierno - Farmacias BA"
              />
            </div>

            <div className="space-y-1.5">
              <Label>Tipo de campaña</Label>
              <Select value={tipo} onValueChange={(v: 'email' | 'whatsapp') => setTipo(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="email">Email</SelectItem>
                  <SelectItem value="whatsapp">WhatsApp</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="border-t pt-4">
              <p className="text-sm font-semibold text-slate-700 mb-3">Segmento de leads</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Provincia</Label>
                  <Select value={segProvincia} onValueChange={setSegProvincia}>
                    <SelectTrigger>
                      <SelectValue placeholder="Todas" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Todas las provincias</SelectItem>
                      {PROVINCIAS.map((p) => (
                        <SelectItem key={p} value={p}>{p}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label>Rubro</Label>
                  <Select value={segRubro} onValueChange={setSegRubro}>
                    <SelectTrigger>
                      <SelectValue placeholder="Todos" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Todos los rubros</SelectItem>
                      {RUBROS.map((r) => (
                        <SelectItem key={r} value={r}>{r}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label>Estado de lead</Label>
                  <Select value={segEstado} onValueChange={setSegEstado}>
                    <SelectTrigger>
                      <SelectValue placeholder="Todos" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Todos los estados</SelectItem>
                      <SelectItem value="nuevo">Nuevo</SelectItem>
                      <SelectItem value="contactado">Contactado</SelectItem>
                      <SelectItem value="interesado">Interesado</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="flex items-center gap-2 mt-3">
                <Switch id="solo-email-seg" checked={segSoloEmail} onCheckedChange={setSegSoloEmail} />
                <Label htmlFor="solo-email-seg" className="cursor-pointer">Solo leads con email</Label>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button
                onClick={() => goToStep(2)}
                disabled={!nombre.trim()}
              >
                Siguiente
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Contenido */}
      {step === 2 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Paso 2: Contenido</CardTitle>
              <Button
                variant="outline"
                size="sm"
                onClick={handleGenerateAI}
                disabled={generatingAI}
                className="gap-2"
              >
                {generatingAI ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4 text-amber-500" />
                )}
                Generar con IA
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {tipo === 'email' && (
              <div className="space-y-1.5">
                <Label>Asunto del email *</Label>
                <Input
                  value={asunto}
                  onChange={(e) => setAsunto(e.target.value)}
                  placeholder="Ej: Nuevos productos Kairos para tu negocio"
                />
              </div>
            )}

            <div className="space-y-1.5">
              <Label>
                {tipo === 'email' ? 'Cuerpo del email' : 'Mensaje de WhatsApp'} *
              </Label>
              <Textarea
                value={cuerpo}
                onChange={(e) => setCuerpo(e.target.value)}
                placeholder={
                  tipo === 'email'
                    ? 'Hola {nombre},\n\nTe escribimos desde Kairos...'
                    : 'Hola {nombre}! Te contactamos desde Kairos...'
                }
                rows={12}
                className="font-mono text-sm"
              />
              <p className="text-xs text-slate-500">
                Podés usar {'{nombre}'}, {'{empresa}'} como variables personalizadas.
              </p>
            </div>

            <div className="flex justify-between pt-2">
              <Button variant="outline" onClick={() => setStep(1)}>
                <ArrowLeft className="w-4 h-4 mr-2" />
                Anterior
              </Button>
              <Button
                onClick={() => goToStep(3)}
                disabled={!cuerpo.trim() || (tipo === 'email' && !asunto.trim())}
              >
                Siguiente
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Revisar */}
      {step === 3 && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Paso 3: Revisar y Enviar</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Summary */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-slate-50 p-3 rounded-lg">
                  <p className="text-slate-500">Nombre</p>
                  <p className="font-semibold text-slate-900 mt-0.5">{nombre}</p>
                </div>
                <div className="bg-slate-50 p-3 rounded-lg">
                  <p className="text-slate-500">Tipo</p>
                  <p className="font-semibold text-slate-900 mt-0.5 capitalize">{tipo}</p>
                </div>
                <div className="bg-slate-50 p-3 rounded-lg">
                  <p className="text-slate-500">Segmento</p>
                  <p className="font-semibold text-slate-900 mt-0.5">
                    {[
                      segProvincia !== 'all' && segProvincia,
                      segRubro !== 'all' && segRubro,
                      segEstado !== 'all' && segEstado,
                    ].filter(Boolean).join(', ') || 'Todos los leads'}
                    {segSoloEmail && ' (con email)'}
                  </p>
                </div>
                <div className="bg-slate-50 p-3 rounded-lg">
                  <p className="text-slate-500">Leads que recibirán</p>
                  <p className="font-semibold text-slate-900 mt-0.5">
                    {loadingCount ? (
                      <Loader2 className="w-4 h-4 animate-spin inline" />
                    ) : leadsCount !== null ? (
                      `${leadsCount.toLocaleString('es-AR')} leads`
                    ) : '—'}
                  </p>
                </div>
              </div>

              {/* Email Preview */}
              <div className="border rounded-lg overflow-hidden">
                <div className="bg-slate-100 px-4 py-2 border-b">
                  <p className="text-xs text-slate-500 font-medium">PREVIEW</p>
                  {tipo === 'email' && asunto && (
                    <p className="text-sm font-semibold text-slate-900 mt-0.5">Asunto: {asunto}</p>
                  )}
                </div>
                <div className="p-4 bg-white">
                  <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                    {cuerpo || <span className="text-slate-400 italic">Sin contenido</span>}
                  </p>
                </div>
              </div>

              <div className="flex justify-between pt-2">
                <Button variant="outline" onClick={() => setStep(2)}>
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Anterior
                </Button>
                <Button
                  onClick={handleSend}
                  disabled={sending}
                  className="bg-emerald-600 hover:bg-emerald-700 gap-2"
                >
                  {sending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                  Enviar Campaña
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}

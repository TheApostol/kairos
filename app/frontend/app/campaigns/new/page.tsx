'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createCampaign, sendCampaign, generateCampaignText, getLeads } from '@/lib/api'
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
import { ArrowLeft, ArrowRight, Loader2, Sparkles, Send, CheckCircle2, Zap } from 'lucide-react'
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

interface SeasonalTemplate {
  label: string
  nombre: string
  asunto: string
  cuerpo: string
  cuerpo_html?: string
}

const SEASONAL_TEMPLATES: SeasonalTemplate[] = [
  {
    label: '🎄 Navidad',
    nombre: 'Campaña Navidad',
    asunto: '¡Felices Fiestas! Novedades Kairos para cerrar el año',
    cuerpo:
      'Hola {empresa},\n\nEn estas fiestas queremos agradecerte por tu confianza durante todo el año y contarte que tenemos productos especiales para la temporada.\n\nSeteos de regalo, sahumerios aromáticos y velas de soja son perfectos para las fiestas y para regalar. ¡Consultanos por cantidades y precios especiales!\n\n¡Felices fiestas!\nEquipo Kairos',
  },
  {
    label: '🎆 Año Nuevo',
    nombre: 'Campaña Año Nuevo',
    asunto: '¡Nuevo año, nuevos productos Kairos! Arrancá con todo',
    cuerpo:
      'Hola {empresa},\n\n¡Feliz Año Nuevo! Arrancamos el año con novedades en nuestro catálogo y precios actualizados especiales para vos.\n\nEste año queremos seguir creciendo juntos. Contactanos para conocer las novedades y hacer tu primer pedido del año con beneficios exclusivos.\n\n¡Hasta pronto!\nEquipo Kairos',
  },
  {
    label: '💕 Día de los Enamorados',
    nombre: 'Campaña San Valentín',
    asunto: 'Día de los enamorados: sets románticos Kairos',
    cuerpo:
      'Hola {empresa},\n\nEl 14 de febrero es una fecha clave para tu negocio. Nuestros sets de velas aromáticas, sahumerios y aceites esenciales son el regalo perfecto para la ocasión.\n\nConsultanos por packs especiales para San Valentín y diferenciá tu oferta esta temporada.\n\nSaludos,\nEquipo Kairos',
  },
  {
    label: '👩 Día de la Madre',
    nombre: 'Campaña Día de la Madre',
    asunto: 'Día de la Madre: los mejores regalos bienestar',
    cuerpo:
      'Hola {empresa},\n\nEl Día de la Madre es una de las fechas de mayor venta del año. Nuestros productos de bienestar y aromaterapia son regalos que toda mamá valora.\n\nTenemos opciones para todos los presupuestos y podemos ayudarte a armar combos especiales. ¡Consultanos con anticipación para asegurar stock!\n\nSaludos,\nEquipo Kairos',
  },
  {
    label: '👨 Día del Padre',
    nombre: 'Campaña Día del Padre',
    asunto: 'Día del Padre: sorprendelos con bienestar natural',
    cuerpo:
      'Hola {empresa},\n\nEste Día del Padre, los productos de bienestar natural son una opción diferente y muy valorada. Nuestras fragancias para el hogar y kits de relajación son una excelente alternativa.\n\n¿Querés incluirlos en tu propuesta? Contactanos y te armamos una oferta especial.\n\nSaludos,\nEquipo Kairos',
  },
  {
    label: '👫 Día del Amigo',
    nombre: 'Campaña Día del Amigo',
    asunto: 'Día del Amigo: compartí el bienestar con tus clientes',
    cuerpo:
      'Hola {empresa},\n\nEl 20 de julio es la oportunidad perfecta para ofrecer a tus clientes algo especial para compartir. Nuestros productos de aromaterapia y bienestar son ideales para regalar entre amigos.\n\nConsultanos por nuestras promociones especiales para esta fecha.\n\n¡Saludos!\nEquipo Kairos',
  },
  {
    label: '🌿 Promo General',
    nombre: 'Campaña Producto Nuevo',
    asunto: 'Novedad en Kairos: productos que van a sorprender a tus clientes',
    cuerpo:
      'Hola {empresa},\n\nTe escribimos desde Kairos para contarte que incorporamos novedades en nuestro catálogo que creemos que van a interesarle a tus clientes.\n\nSi querés conocer más detalles, precios mayoristas y disponibilidad de stock, respondé este email o contactanos directamente.\n\n¡Hasta pronto!\nEquipo Kairos',
  },
]

export default function NewCampaignPage() {
  const router = useRouter()
  const [step, setStep] = useState(1)
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [generatingAI, setGeneratingAI] = useState(false)
  const [leadsCount, setLeadsCount] = useState<number | null>(null)
  const [loadingCount, setLoadingCount] = useState(false)
  const [showTemplates, setShowTemplates] = useState(false)

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
  const [cuerpoHtml, setCuerpoHtml] = useState('')
  const [followup1, setFollowup1] = useState('')
  const [followup2, setFollowup2] = useState('')

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

  const applyTemplate = (tpl: SeasonalTemplate) => {
    setNombre(tpl.nombre)
    setAsunto(tpl.asunto)
    setCuerpo(tpl.cuerpo)
    setCuerpoHtml(tpl.cuerpo_html || '')
    setShowTemplates(false)
    setStep(2)
  }

  const handleGenerateAI = async () => {
    setGeneratingAI(true)
    try {
      const segDesc = [
        segRubro !== 'all' ? segRubro : 'tiendas holísticas y de sahumerios',
        segProvincia !== 'all' ? `en ${segProvincia}` : 'en Argentina',
      ].join(' ')
      const result = await generateCampaignText({
        tipo,
        segmento_desc: segDesc,
      })
      if (result.asunto) setAsunto(result.asunto)
      if (result.cuerpo) setCuerpo(result.cuerpo)
      if (result.cuerpo_html) setCuerpoHtml(result.cuerpo_html)
      if (result.followup_1) setFollowup1(result.followup_1)
      if (result.followup_2) setFollowup2(result.followup_2)
    } catch {
    } finally {
      setGeneratingAI(false)
    }
  }

  const handleSend = async () => {
    setSending(true)
    try {
      const campaign = await createCampaign({
        nombre,
        tipo,
        asunto,
        cuerpo,
        cuerpo_html: cuerpoHtml || undefined,
        segmento: buildSegmentParams(),
        followup_1: followup1 || undefined,
        followup_2: followup2 || undefined,
      })
      await sendCampaign(campaign.id)
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

  const resetForm = () => {
    setSent(false)
    setStep(1)
    setNombre('')
    setAsunto('')
    setCuerpo('')
    setCuerpoHtml('')
    setFollowup1('')
    setFollowup2('')
  }

  if (sent) {
    return (
      <div className="max-w-lg mx-auto mt-16 text-center space-y-4">
        <CheckCircle2 className="w-16 h-16 text-emerald-500 mx-auto" />
        <h2 className="text-2xl font-bold text-slate-900">Campaña enviada</h2>
        <p className="text-slate-500">Tu campaña fue creada y enviada exitosamente.</p>
        {(followup1 || followup2) && (
          <p className="text-sm text-blue-600 bg-blue-50 p-3 rounded-lg">
            Los seguimientos automáticos están configurados y se enviarán a los 3 y 7 días.
          </p>
        )}
        <div className="flex gap-3 justify-center">
          <Button variant="outline" onClick={() => router.push('/campaigns')}>
            Ver Campañas
          </Button>
          <Button onClick={resetForm}>
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
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">Nueva Campaña</h1>
          <p className="text-slate-500 mt-0.5">Crea y envía una campaña a tus leads</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowTemplates(!showTemplates)}
          className="gap-2 border-amber-400 text-amber-700 hover:bg-amber-50"
        >
          <Zap className="w-4 h-4" />
          Templates
        </Button>
      </div>

      {/* Seasonal Templates Panel */}
      {showTemplates && (
        <Card className="border-amber-200 bg-amber-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-amber-800">Templates estacionales — click para usar</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {SEASONAL_TEMPLATES.map((tpl) => (
                <button
                  key={tpl.label}
                  onClick={() => applyTemplate(tpl)}
                  className="text-left p-3 rounded-lg bg-white border border-amber-200 hover:border-amber-400 hover:bg-amber-50 transition-colors"
                >
                  <p className="text-sm font-semibold text-slate-800">{tpl.label}</p>
                  <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{tpl.asunto}</p>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

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
                    ? 'Hola {empresa},\n\nTe escribimos desde Kairos...'
                    : 'Hola {empresa}! Te contactamos desde Kairos...'
                }
                rows={10}
                className="font-mono text-sm"
              />
              <p className="text-xs text-slate-500">
                Podés usar <code className="bg-slate-100 px-1 rounded">{'{empresa}'}</code>,{' '}
                <code className="bg-slate-100 px-1 rounded">{'{ciudad}'}</code>,{' '}
                <code className="bg-slate-100 px-1 rounded">{'{provincia}'}</code> como variables.
              </p>
            </div>

            {tipo === 'email' && (
              <div className="border-t pt-4 space-y-3">
                <p className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  Seguimientos automáticos
                  <span className="text-xs font-normal text-slate-400">(generados por IA — editables)</span>
                </p>
                <div className="space-y-1.5">
                  <Label className="text-xs text-slate-500">Seguimiento 3 días (si no abrió)</Label>
                  <Textarea
                    value={followup1}
                    onChange={(e) => setFollowup1(e.target.value)}
                    placeholder="Mensaje de seguimiento a los 3 días..."
                    rows={3}
                    className="text-sm"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs text-slate-500">Seguimiento 7 días (último contacto)</Label>
                  <Textarea
                    value={followup2}
                    onChange={(e) => setFollowup2(e.target.value)}
                    placeholder="Mensaje de cierre a los 7 días..."
                    rows={3}
                    className="text-sm"
                  />
                </div>
              </div>
            )}

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

              {(followup1 || followup2) && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">
                  <p className="font-semibold">Seguimientos automáticos configurados</p>
                  <p className="text-xs mt-1 text-blue-600">
                    {followup1 ? '✓ Seguimiento a 3 días ' : ''}
                    {followup2 ? '✓ Seguimiento a 7 días' : ''}
                  </p>
                </div>
              )}

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

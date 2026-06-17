'use client'

import { Fragment, useEffect, useState, useRef } from 'react'
import { getScraperHistory, runScraper, runEnrichment, cancelScraperJob, getEventSourceUrl, SCRAPER_SOURCES, DEFAULT_SCRAPER_SOURCES } from '@/lib/api'
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
import { Play, RefreshCw, Loader2, CheckCircle2, XCircle, Clock, AlertCircle, StopCircle, Zap, ChevronDown, ChevronUp } from 'lucide-react'
import { format, formatDistanceToNow } from 'date-fns'
import { es } from 'date-fns/locale'

interface SourceStat {
  found: number
  new: number
  status: string
  error?: string
}

interface ScraperDetails {
  sources?: Record<string, SourceStat>
}

interface EnrichmentDetails {
  websites_discovered?: number
  emails_found?: number
  instagram_found?: number
  whatsapp_found?: number
  telefono_found?: number
  no_website?: number
}

interface ScraperJob {
  id: number
  started_at?: string
  finished_at?: string
  estado: string
  total_encontrados?: number
  nuevos_agregados?: number
  error?: string
  progress?: number
  total?: number
  tipo?: 'scraper' | 'enrichment'
  sources?: string[]
  details?: ScraperDetails & EnrichmentDetails
}

type RunState = 'idle' | 'running' | 'done' | 'error'

const SOURCE_LABELS: Record<string, string> = Object.fromEntries(
  SCRAPER_SOURCES.map((s) => [s.id, s.label])
)

const SOURCE_STATUS_LABELS: Record<string, string> = {
  completed: 'Completado',
  skipped: 'Omitida',
  failed: 'Falló',
  running: 'Corriendo',
  pending: 'Pendiente',
  unknown_source: 'Desconocida',
}

function ScraperReportTable({ sources }: { sources: Record<string, SourceStat> }) {
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Fuente</TableHead>
            <TableHead>Encontrados</TableHead>
            <TableHead>Nuevos</TableHead>
            <TableHead>Estado</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(sources).map(([id, stat]) => (
            <TableRow key={id}>
              <TableCell className="text-sm font-medium text-slate-700">{SOURCE_LABELS[id] ?? id}</TableCell>
              <TableCell className="text-sm">{stat.found}</TableCell>
              <TableCell className="text-sm text-emerald-700 font-semibold">+{stat.new}</TableCell>
              <TableCell>
                <Badge
                  variant={stat.status === 'completed' ? 'success' : stat.status === 'failed' ? 'danger' : stat.status === 'skipped' ? 'warning' : 'secondary'}
                  className="text-[10px]"
                  title={stat.error}
                >
                  {SOURCE_STATUS_LABELS[stat.status] ?? stat.status}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function EnrichmentReportGrid({ details }: { details: EnrichmentDetails }) {
  const cards = [
    { label: 'Emails encontrados', value: details.emails_found ?? 0, color: 'text-emerald-700 bg-emerald-50' },
    { label: 'Teléfonos encontrados', value: details.telefono_found ?? 0, color: 'text-blue-700 bg-blue-50' },
    { label: 'Instagram encontrado', value: details.instagram_found ?? 0, color: 'text-violet-700 bg-violet-50' },
    { label: 'WhatsApp encontrado', value: details.whatsapp_found ?? 0, color: 'text-green-700 bg-green-50' },
    { label: 'Sitios web descubiertos', value: details.websites_discovered ?? 0, color: 'text-amber-700 bg-amber-50' },
    { label: 'Sin sitio web', value: details.no_website ?? 0, color: 'text-slate-600 bg-slate-50' },
  ]
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {cards.map(({ label, value, color }) => (
        <div key={label} className={`rounded-lg px-3 py-2 text-center ${color}`}>
          <p className="text-xs opacity-80">{label}</p>
          <p className="text-lg font-bold">{value.toLocaleString('es-AR')}</p>
        </div>
      ))}
    </div>
  )
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '—'
  try {
    return format(new Date(dateStr), "d MMM yyyy, HH:mm", { locale: es })
  } catch {
    return dateStr
  }
}

function JobStatusBadge({ estado }: { estado: string }) {
  const map: Record<string, { variant: 'success' | 'danger' | 'warning' | 'secondary'; icon: typeof CheckCircle2 }> = {
    completado: { variant: 'success', icon: CheckCircle2 },
    error: { variant: 'danger', icon: XCircle },
    corriendo: { variant: 'warning', icon: Loader2 },
    pendiente: { variant: 'secondary', icon: Clock },
  }
  const cfg = map[estado] ?? { variant: 'secondary' as const, icon: Clock }
  const Icon = cfg.icon
  return (
    <Badge variant={cfg.variant} className="gap-1 capitalize">
      <Icon className={`w-3 h-3 ${estado === 'corriendo' ? 'animate-spin' : ''}`} />
      {estado}
    </Badge>
  )
}

export default function ScraperPage() {
  const [history, setHistory] = useState<ScraperJob[]>([])
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [scraperState, setScraperState] = useState<RunState>('idle')
  const [enrichState, setEnrichState] = useState<RunState>('idle')
  const [scraperError, setScraperError] = useState('')
  const [enrichError, setEnrichError] = useState('')

  // Scraper progress
  const [progress, setProgress] = useState(0)
  const [currentQuery, setCurrentQuery] = useState('')
  const [logLines, setLogLines] = useState<string[]>([])
  const [scraperReport, setScraperReport] = useState<Record<string, SourceStat> | null>(null)
  const logRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  // Enricher progress
  const [enrichProgress, setEnrichProgress] = useState(0)
  const [enrichFound, setEnrichFound] = useState(0)
  const [enrichTotal, setEnrichTotal] = useState(0)
  const [enrichStartedAt, setEnrichStartedAt] = useState<Date | null>(null)
  const [enrichReport, setEnrichReport] = useState<EnrichmentDetails | null>(null)
  const enrichIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [scraperJobId, setScraperJobId] = useState<string | null>(null)
  const [enrichJobId, setEnrichJobId] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [cancellingId, setCancellingId] = useState<number | null>(null)
  const [expandedJobId, setExpandedJobId] = useState<number | null>(null)
  const autoCombinedRef = useRef(false)

  // Source selector — which free/paid lead sources to query
  const [selectedSources, setSelectedSources] = useState<string[]>([...DEFAULT_SCRAPER_SOURCES])
  const toggleSource = (id: string) => {
    setSelectedSources((prev) => prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id])
  }

  const cancelJob = async (jobId: number) => {
    setCancellingId(jobId)
    try {
      await cancelScraperJob(jobId)
      await fetchHistory()
      setScraperState((prev) => prev === 'running' ? 'idle' : prev)
      setEnrichState((prev) => prev === 'running' ? 'idle' : prev)
    } catch {}
    finally { setCancellingId(null) }
  }

  const fetchHistory = async () => {
    setRefreshing(true)
    try {
      const data = await getScraperHistory()
      const jobs: ScraperJob[] = data.items ?? data ?? []
      setHistory(jobs)

      // Sync UI state with actual job status from DB
      const runningJob = jobs.find((j) => j.estado === 'corriendo' || j.estado === 'pendiente')
      if (!runningJob) {
        // No running jobs → reset any stuck running states
        setScraperState((prev) => prev === 'running' ? 'idle' : prev)
        setEnrichState((prev) => prev === 'running' ? 'idle' : prev)
      }
    } catch {}
    finally { setRefreshing(false) }
  }

  useEffect(() => {
    fetchHistory().finally(() => setLoadingHistory(false))
    return () => {
      eventSourceRef.current?.close()
      if (enrichIntervalRef.current) clearInterval(enrichIntervalRef.current)
    }
  }, [])

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logLines])

  const isScraperRunning = scraperState === 'running'
  const isEnrichRunning = enrichState === 'running'
  const anyJobRunning = isScraperRunning || isEnrichRunning

  const stopCurrentJob = async (jobId: string | null, onDone: () => void) => {
    if (!jobId) return
    try {
      await cancelScraperJob(jobId)
      onDone()
      await fetchHistory()
    } catch {}
  }

  const startCombined = async () => {
    autoCombinedRef.current = true
    await startScraper()
  }

  const startScraper = async () => {
    setScraperState('running')
    setScraperError('')
    setScraperJobId(null)
    setProgress(0)
    setCurrentQuery('')
    setLogLines(['Iniciando scraper...'])
    setScraperReport(null)

    try {
      const res = await runScraper({ sources: selectedSources })
      if (res?.job_id) setScraperJobId(String(res.job_id))

      const es = new EventSource(await getEventSourceUrl('/scraper/progress'))
      eventSourceRef.current = es

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.progress !== undefined) setProgress(Math.min(100, data.progress))
          if (data.query) {
            setCurrentQuery(data.query)
            setLogLines((prev) => [...prev.slice(-49), `[${new Date().toLocaleTimeString('es-AR')}] ${data.query}`])
          }
          if (data.error) {
            es.close()
            autoCombinedRef.current = false
            setScraperState('error')
            setLogLines((prev) => [...prev, `ERROR: ${data.error}`])
            if (data.details?.sources) setScraperReport(data.details.sources)
            fetchHistory()
            return
          }
          if (data.done || data.progress >= 100) {
            es.close()
            setScraperState('done')
            setProgress(100)
            setCurrentQuery('Completado')
            setLogLines((prev) => [...prev, `✓ Encontrados: ${data.total_found ?? 0} · Nuevos: ${data.new_found ?? 0}`])
            if (data.details?.sources) setScraperReport(data.details.sources)
            fetchHistory()
            if (autoCombinedRef.current) {
              autoCombinedRef.current = false
              setLogLines((prev) => [...prev, '→ Iniciando enriquecimiento automático...'])
              setTimeout(() => startEnrichment(), 1500)
            }
          }
        } catch {}
      }

      es.onerror = () => {
        es.close()
        setScraperState((prev) => prev === 'running' ? 'done' : prev)
        fetchHistory()
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg.includes('409') || msg.includes('corriendo')) {
        setScraperError('Ya hay un job corriendo. Refrescá el historial para ver el estado.')
      } else {
        setScraperError('Error al iniciar el scraper.')
      }
      setScraperState('error')
      setLogLines((prev) => [...prev, `Error al iniciar el scraper`])
    }
  }

  const startEnrichment = async () => {
    setEnrichState('running')
    setEnrichError('')
    setEnrichProgress(0)
    setEnrichFound(0)
    setEnrichTotal(0)
    setEnrichReport(null)
    setEnrichStartedAt(new Date())

    try {
      const res = await runEnrichment()
      const jobId = res?.job_id
      if (jobId) setEnrichJobId(String(jobId))

      // Poll job status every 4s for live progress
      if (enrichIntervalRef.current) clearInterval(enrichIntervalRef.current)
      enrichIntervalRef.current = setInterval(async () => {
        const data = await getScraperHistory()
        const jobs: ScraperJob[] = data.items ?? data ?? []

        // Find the enrichment job we just started (most recent enrichment)
        const enrichJob = jobId
          ? jobs.find((j) => String(j.id) === String(jobId))
          : jobs.find((j) => j.tipo === 'enrichment')

        if (enrichJob) {
          setEnrichProgress(enrichJob.progress ?? 0)
          setEnrichFound(enrichJob.nuevos_agregados ?? 0)
          setEnrichTotal(enrichJob.total_encontrados ?? 0)
          if (enrichJob.details) setEnrichReport(enrichJob.details)

          if (enrichJob.estado === 'completado' || enrichJob.estado === 'error') {
            clearInterval(enrichIntervalRef.current!)
            enrichIntervalRef.current = null
            setEnrichState(enrichJob.estado === 'completado' ? 'done' : 'error')
            if (enrichJob.estado === 'error') setEnrichError(enrichJob.error ?? 'Error desconocido')
            setHistory(jobs)
          }
        }
      }, 4000)

      // Safety timeout after 15 minutes
      setTimeout(() => {
        if (enrichIntervalRef.current) {
          clearInterval(enrichIntervalRef.current)
          enrichIntervalRef.current = null
          setEnrichState((prev) => prev === 'running' ? 'done' : prev)
          fetchHistory()
        }
      }, 900000)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg.includes('409') || msg.includes('corriendo')) {
        setEnrichError('Ya hay un job corriendo. Esperá a que termine.')
      } else {
        setEnrichError('Error al iniciar el enriquecimiento.')
      }
      setEnrichState('error')
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: '#4A3728' }}>Scraper de Leads</h1>
        <p className="mt-1" style={{ color: '#6B4F3A' }}>Busca tiendas holísticas, esotéricas y de sahumerios en toda Argentina</p>
      </div>

      {/* Action Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Todo en uno */}
        <Card className={`border-2 transition-all sm:col-span-1 ${anyJobRunning ? 'border-amber-400' : 'border-amber-200 hover:border-amber-400'}`} style={{ background: 'linear-gradient(135deg,#fffbeb,#fef3c7)' }}>
          <CardContent className="pt-6 pb-6">
            <div className="text-center space-y-4">
              <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto">
                {anyJobRunning ? (
                  <Loader2 className="w-8 h-8 text-amber-600 animate-spin" />
                ) : (
                  <Zap className="w-8 h-8 text-amber-600" />
                )}
              </div>
              <div>
                <h3 className="font-semibold text-slate-900">Todo en uno</h3>
                <p className="text-xs text-slate-500 mt-1">Scraper + enriquecimiento automático</p>
              </div>
              <Button
                onClick={startCombined}
                disabled={anyJobRunning || selectedSources.length === 0}
                className="w-full gap-2 text-white"
                style={{ backgroundColor: '#C9A040' }}
                size="lg"
              >
                {anyJobRunning ? <><Loader2 className="w-5 h-5 animate-spin" />Corriendo...</> : <><Zap className="w-5 h-5" />Iniciar Todo</>}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Scraper */}
        <Card className={`border-2 transition-all ${isScraperRunning ? 'border-green-400' : 'border-transparent hover:border-slate-200'}`}>
          <CardContent className="pt-6 pb-6">
            <div className="text-center space-y-4">
              <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto">
                {isScraperRunning ? (
                  <Loader2 className="w-8 h-8 text-emerald-600 animate-spin" />
                ) : scraperState === 'done' ? (
                  <CheckCircle2 className="w-8 h-8 text-emerald-600" />
                ) : scraperState === 'error' ? (
                  <XCircle className="w-8 h-8 text-red-500" />
                ) : (
                  <Play className="w-8 h-8 text-emerald-600" />
                )}
              </div>
              <div>
                <h3 className="font-semibold text-slate-900">Ejecutar Scraper</h3>
                <p className="text-sm text-slate-500 mt-1">Busca nuevos leads en directorios y webs</p>
              </div>
              {scraperError && (
                <div className="flex items-center gap-2 text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg text-left">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  {scraperError}
                </div>
              )}
              <Button
                onClick={startScraper}
                disabled={anyJobRunning || selectedSources.length === 0}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white gap-2"
                size="lg"
              >
                {isScraperRunning ? <><Loader2 className="w-5 h-5 animate-spin" />Corriendo...</> : <><Play className="w-5 h-5" />Ejecutar Scraper</>}
              </Button>
              {isScraperRunning && scraperJobId && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full border-red-300 text-red-600 hover:bg-red-50 gap-2"
                  onClick={() => stopCurrentJob(scraperJobId, () => { setScraperState('idle'); setScraperJobId(null); eventSourceRef.current?.close() })}
                >
                  <StopCircle className="w-4 h-4" />
                  Detener scraper
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Enricher */}
        <Card className={`border-2 transition-all ${isEnrichRunning ? 'border-blue-400' : 'border-transparent hover:border-slate-200'}`}>
          <CardContent className="pt-6 pb-6">
            <div className="text-center space-y-4">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto">
                {isEnrichRunning ? (
                  <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
                ) : enrichState === 'done' ? (
                  <CheckCircle2 className="w-8 h-8 text-blue-600" />
                ) : enrichState === 'error' ? (
                  <XCircle className="w-8 h-8 text-red-500" />
                ) : (
                  <RefreshCw className="w-8 h-8 text-blue-600" />
                )}
              </div>
              <div>
                <h3 className="font-semibold text-slate-900">Enriquecer Leads</h3>
                <p className="text-sm text-slate-500 mt-1">Extrae emails y teléfonos de websites</p>
              </div>
              {enrichError && (
                <div className="flex items-center gap-2 text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg text-left">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  {enrichError}
                </div>
              )}
              <Button
                onClick={startEnrichment}
                disabled={anyJobRunning}
                variant="outline"
                className="w-full border-blue-300 text-blue-700 hover:bg-blue-50 gap-2"
                size="lg"
              >
                {isEnrichRunning ? <><Loader2 className="w-5 h-5 animate-spin" />Enriqueciendo...</> : <><RefreshCw className="w-5 h-5" />Enriquecer Leads</>}
              </Button>
              {isEnrichRunning && enrichJobId && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full border-red-300 text-red-600 hover:bg-red-50 gap-2"
                  onClick={() => stopCurrentJob(enrichJobId, () => { setEnrichState('idle'); setEnrichJobId(null); if (enrichIntervalRef.current) { clearInterval(enrichIntervalRef.current); enrichIntervalRef.current = null } })}
                >
                  <StopCircle className="w-4 h-4" />
                  Detener enriquecimiento
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Source Selector */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Fuentes de datos</CardTitle>
          <p className="text-sm text-slate-500">Elegí qué fuentes consultar al ejecutar el scraper</p>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {SCRAPER_SOURCES.map((source) => {
              const checked = selectedSources.includes(source.id)
              return (
                <label
                  key={source.id}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm cursor-pointer transition-colors ${
                    checked ? 'border-emerald-400 bg-emerald-50 text-emerald-800' : 'border-slate-200 text-slate-600 hover:border-slate-300'
                  } ${anyJobRunning ? 'opacity-60 pointer-events-none' : ''}`}
                >
                  <input
                    type="checkbox"
                    className="accent-emerald-600"
                    checked={checked}
                    disabled={anyJobRunning}
                    onChange={() => toggleSource(source.id)}
                  />
                  {source.label}
                  {'requiresApiKey' in source && source.requiresApiKey && (
                    <Badge variant="secondary" className="text-[10px]">requiere API key</Badge>
                  )}
                  {'experimental' in source && source.experimental && (
                    <Badge variant="warning" className="text-[10px]">experimental</Badge>
                  )}
                </label>
              )
            })}
          </div>
          {selectedSources.length === 0 && (
            <p className="text-xs text-red-600 mt-2">Elegí al menos una fuente para poder ejecutar el scraper.</p>
          )}
        </CardContent>
      </Card>

      {/* Scraper Progress Panel */}
      {(isScraperRunning || scraperState === 'done' || scraperState === 'error') && logLines.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">
                {isScraperRunning ? 'Scraper en ejecución' : scraperState === 'done' ? 'Scraper completado' : 'Error en scraper'}
              </CardTitle>
              {isScraperRunning && <Badge variant="warning" className="gap-1"><Loader2 className="w-3 h-3 animate-spin" />Corriendo</Badge>}
              {scraperState === 'done' && <Badge variant="success">Completado</Badge>}
              {scraperState === 'error' && <Badge variant="danger">Error</Badge>}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {isScraperRunning && (
              <>
                <div className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-600">Progreso</span>
                    <span className="font-semibold text-slate-900">{progress}%</span>
                  </div>
                  <Progress value={progress} className="h-3" />
                </div>
                {currentQuery && (
                  <div className="flex items-center gap-2 text-sm text-slate-600 bg-slate-50 px-3 py-2 rounded-lg">
                    <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
                    <span className="truncate">{currentQuery}</span>
                  </div>
                )}
              </>
            )}
            <div ref={logRef} className="bg-slate-900 rounded-lg p-4 h-40 overflow-y-auto font-mono text-xs">
              {logLines.map((line, i) => (
                <div key={i} className={line.startsWith('ERROR') ? 'text-red-400' : line.startsWith('✓') ? 'text-emerald-400' : 'text-slate-300'}>
                  {line}
                </div>
              ))}
            </div>
            {!isScraperRunning && scraperReport && Object.keys(scraperReport).length > 0 && (
              <div>
                <p className="text-sm font-semibold text-slate-700 mb-2">Reporte por fuente</p>
                <ScraperReportTable sources={scraperReport} />
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Enricher Progress Panel */}
      {(isEnrichRunning || enrichState === 'done' || enrichState === 'error') && (
        <Card className={isEnrichRunning ? 'border-blue-200' : ''}>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">
                {isEnrichRunning ? 'Enriquecimiento en progreso' : enrichState === 'done' ? 'Enriquecimiento completado' : 'Error en enriquecimiento'}
              </CardTitle>
              {isEnrichRunning && <Badge variant="warning" className="gap-1"><Loader2 className="w-3 h-3 animate-spin" />Corriendo</Badge>}
              {enrichState === 'done' && <Badge variant="success">Completado</Badge>}
              {enrichState === 'error' && <Badge variant="danger">Error</Badge>}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Progress bar */}
            <div className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-slate-600">Progreso</span>
                <span className="font-semibold text-slate-900">{enrichProgress}%</span>
              </div>
              <Progress value={enrichProgress} className="h-3" />
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-slate-50 rounded-lg px-3 py-2 text-center">
                <p className="text-xs text-slate-500">Procesados</p>
                <p className="text-lg font-bold text-slate-800">
                  {enrichTotal > 0 ? Math.round((enrichProgress / 100) * enrichTotal) : '—'}
                  {enrichTotal > 0 && <span className="text-xs font-normal text-slate-400"> / {enrichTotal}</span>}
                </p>
              </div>
              <div className="bg-emerald-50 rounded-lg px-3 py-2 text-center">
                <p className="text-xs text-slate-500">Enriquecidos</p>
                <p className="text-lg font-bold text-emerald-700">+{enrichFound}</p>
              </div>
              <div className="bg-blue-50 rounded-lg px-3 py-2 text-center">
                <p className="text-xs text-slate-500">Tiempo</p>
                <p className="text-sm font-semibold text-blue-700">
                  {enrichStartedAt
                    ? formatDistanceToNow(enrichStartedAt, { locale: es })
                    : '—'}
                </p>
              </div>
            </div>

            {isEnrichRunning && (
              <p className="text-xs text-slate-400 text-center">
                Actualizando cada 4 segundos · El proceso puede tomar varios minutos
              </p>
            )}

            {enrichState === 'done' && (
              <>
                <p className="text-sm text-emerald-700 font-medium text-center">
                  ✓ {enrichFound} lead{enrichFound !== 1 ? 's' : ''} enriquecido{enrichFound !== 1 ? 's' : ''} de {enrichTotal} procesados
                </p>
                {enrichReport && (
                  <div>
                    <p className="text-sm font-semibold text-slate-700 mb-2">Reporte de enriquecimiento</p>
                    <EnrichmentReportGrid details={enrichReport} />
                  </div>
                )}
              </>
            )}

            {enrichState === 'error' && enrichError && (
              <p className="text-sm text-red-600 text-center">{enrichError}</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* History Table */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Historial de Jobs</CardTitle>
            <Button variant="ghost" size="sm" onClick={fetchHistory} disabled={refreshing}>
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {loadingHistory ? (
            <div className="flex items-center justify-center h-32">
              <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
            </div>
          ) : history.length === 0 ? (
            <div className="text-center py-8 text-slate-400">
              <Clock className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p className="text-sm">Sin historial de ejecuciones</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table className="min-w-[600px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Tipo</TableHead>
                    <TableHead>Fuentes</TableHead>
                    <TableHead>Inicio</TableHead>
                    <TableHead>Fin</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead>Progreso</TableHead>
                    <TableHead>Total</TableHead>
                    <TableHead>Nuevos</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((job) => (
                    <Fragment key={job.id}>
                      <TableRow>
                        <TableCell>
                          <Badge variant={job.tipo === 'enrichment' ? 'secondary' : 'warning'} className="text-xs capitalize">
                            {job.tipo === 'enrichment' ? 'Enriquec.' : 'Scraper'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-slate-600 text-xs max-w-[180px] truncate">
                          {job.sources?.length ? job.sources.join(', ') : '—'}
                        </TableCell>
                        <TableCell className="text-slate-600 text-sm">{formatDate(job.started_at)}</TableCell>
                        <TableCell className="text-slate-600 text-sm">{formatDate(job.finished_at)}</TableCell>
                        <TableCell><JobStatusBadge estado={job.estado} /></TableCell>
                        <TableCell>
                          {job.estado === 'corriendo' || job.estado === 'pendiente' ? (
                            <div className="flex items-center gap-2">
                              <Progress value={job.progress ?? 0} className="h-1.5 w-20" />
                              <span className="text-xs text-slate-500">{job.progress ?? 0}%</span>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-400">{job.progress ?? 0}%</span>
                          )}
                        </TableCell>
                        <TableCell className="font-medium">{job.total_encontrados?.toLocaleString('es-AR') ?? '—'}</TableCell>
                        <TableCell>
                          {job.nuevos_agregados !== undefined ? (
                            <span className="text-emerald-700 font-semibold">+{job.nuevos_agregados.toLocaleString('es-AR')}</span>
                          ) : '—'}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            {(job.estado === 'corriendo' || job.estado === 'pendiente') && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => cancelJob(job.id)}
                                disabled={cancellingId === job.id}
                                className="text-red-500 hover:text-red-700 hover:bg-red-50 h-7 px-2"
                                title="Cancelar job"
                              >
                                {cancellingId === job.id
                                  ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                  : <StopCircle className="w-3.5 h-3.5" />}
                              </Button>
                            )}
                            {job.details && Object.keys(job.details).length > 0 && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setExpandedJobId((prev) => prev === job.id ? null : job.id)}
                                className="text-slate-500 hover:text-slate-700 h-7 px-2"
                                title="Ver reporte"
                              >
                                {expandedJobId === job.id ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                      {expandedJobId === job.id && job.details && (
                        <TableRow>
                          <TableCell colSpan={9} className="bg-slate-50">
                            {job.tipo === 'enrichment' ? (
                              <EnrichmentReportGrid details={job.details} />
                            ) : job.details.sources ? (
                              <ScraperReportTable sources={job.details.sources} />
                            ) : null}
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

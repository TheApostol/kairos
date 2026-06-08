'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import { getScraperHistory, runScraper, runEnrichment, cancelScraperJob, deleteScraperJob, resetScraper, getApiUrl } from '@/lib/api'
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Play, RefreshCw, Loader2, CheckCircle2, XCircle, Clock, AlertCircle, StopCircle, Trash2, RotateCcw } from 'lucide-react'
import { format, formatDistanceToNow } from 'date-fns'
import { es } from 'date-fns/locale'

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
}

type RunState = 'idle' | 'running' | 'done' | 'error'

function formatDate(dateStr?: string) {
  if (!dateStr) return '—'
  try {
    return format(new Date(dateStr), "d MMM HH:mm", { locale: es })
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
    <Badge variant={cfg.variant} className="gap-1 capitalize text-xs">
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
  const [historyError, setHistoryError] = useState('')

  const [progress, setProgress] = useState(0)
  const [currentQuery, setCurrentQuery] = useState('')
  const [logLines, setLogLines] = useState<string[]>([])
  const logRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  const [enrichProgress, setEnrichProgress] = useState(0)
  const [enrichFound, setEnrichFound] = useState(0)
  const [enrichTotal, setEnrichTotal] = useState(0)
  const [enrichStartedAt, setEnrichStartedAt] = useState<Date | null>(null)
  const enrichIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const historyPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [scraperJobId, setScraperJobId] = useState<string | null>(null)
  const [enrichJobId, setEnrichJobId] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [cancellingId, setCancellingId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [resetting, setResetting] = useState(false)

  const hasActiveJobs = history.some(j => j.estado === 'corriendo' || j.estado === 'pendiente')

  const fetchHistory = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true)
    setHistoryError('')
    try {
      const data = await getScraperHistory()
      const jobs: ScraperJob[] = data.items ?? data ?? []
      setHistory(jobs)
      const runningJob = jobs.find(j => j.estado === 'corriendo' || j.estado === 'pendiente')
      if (!runningJob) {
        setScraperState(prev => prev === 'running' ? 'idle' : prev)
        setEnrichState(prev => prev === 'running' ? 'idle' : prev)
      }
      return jobs
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setHistoryError(`No se pudo cargar el historial: ${msg}`)
      return []
    } finally {
      if (!silent) setRefreshing(false)
    }
  }, [])

  // Auto-poll history every 5s while jobs are running
  useEffect(() => {
    if (hasActiveJobs || scraperState === 'running' || enrichState === 'running') {
      if (!historyPollRef.current) {
        historyPollRef.current = setInterval(() => fetchHistory(true), 5000)
      }
    } else {
      if (historyPollRef.current) {
        clearInterval(historyPollRef.current)
        historyPollRef.current = null
      }
    }
    return () => {
      if (historyPollRef.current) {
        clearInterval(historyPollRef.current)
        historyPollRef.current = null
      }
    }
  }, [hasActiveJobs, scraperState, enrichState, fetchHistory])

  useEffect(() => {
    fetchHistory().finally(() => setLoadingHistory(false))
    return () => {
      eventSourceRef.current?.close()
      if (enrichIntervalRef.current) clearInterval(enrichIntervalRef.current)
      if (historyPollRef.current) clearInterval(historyPollRef.current)
    }
  }, [fetchHistory])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [logLines])

  const isScraperRunning = scraperState === 'running'
  const isEnrichRunning = enrichState === 'running'
  const anyJobRunning = isScraperRunning || isEnrichRunning || hasActiveJobs

  const cancelJob = async (jobId: number) => {
    setCancellingId(jobId)
    try {
      await cancelScraperJob(jobId)
      await fetchHistory()
      setScraperState(prev => prev === 'running' ? 'idle' : prev)
      setEnrichState(prev => prev === 'running' ? 'idle' : prev)
    } catch (e: unknown) {
      alert(`No se pudo cancelar: ${e instanceof Error ? e.message : e}`)
    } finally {
      setCancellingId(null)
    }
  }

  const deleteJob = async (jobId: number) => {
    setDeletingId(jobId)
    try {
      await deleteScraperJob(jobId)
      setHistory(prev => prev.filter(j => j.id !== jobId))
    } catch (e: unknown) {
      alert(`No se pudo eliminar: ${e instanceof Error ? e.message : e}`)
    } finally {
      setDeletingId(null)
    }
  }

  const handleReset = async () => {
    setResetting(true)
    try {
      await resetScraper()
      eventSourceRef.current?.close()
      if (enrichIntervalRef.current) { clearInterval(enrichIntervalRef.current); enrichIntervalRef.current = null }
      setScraperState('idle')
      setEnrichState('idle')
      setScraperJobId(null)
      setEnrichJobId(null)
      setScraperError('')
      setEnrichError('')
      setLogLines([])
      setProgress(0)
      await fetchHistory()
    } catch (e: unknown) {
      alert(`Error al reiniciar: ${e instanceof Error ? e.message : e}`)
    } finally {
      setResetting(false)
    }
  }

  const stopCurrentJob = async (jobId: string | null, onDone: () => void) => {
    if (!jobId) return
    try {
      await cancelScraperJob(jobId)
      onDone()
      await fetchHistory()
    } catch (e: unknown) {
      alert(`No se pudo detener: ${e instanceof Error ? e.message : e}`)
    }
  }

  const startScraper = async () => {
    setScraperState('running')
    setScraperError('')
    setScraperJobId(null)
    setProgress(0)
    setCurrentQuery('')
    setLogLines(['Iniciando scraper...'])

    try {
      const res = await runScraper()
      if (res?.job_id) setScraperJobId(String(res.job_id))

      const evSrc = new EventSource(getApiUrl('/scraper/progress'))
      eventSourceRef.current = evSrc

      evSrc.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.progress !== undefined) setProgress(Math.min(100, data.progress))
          if (data.query) {
            setCurrentQuery(data.query)
            setLogLines(prev => [...prev.slice(-49), `[${new Date().toLocaleTimeString('es-AR')}] ${data.query}`])
          }
          if (data.done || data.progress >= 100) {
            evSrc.close()
            setScraperState('done')
            setProgress(100)
            setCurrentQuery('Completado')
            setLogLines(prev => [...prev, `✓ Encontrados: ${data.total_found ?? 0} · Nuevos: ${data.new_found ?? 0}`])
            fetchHistory()
          }
          if (data.error) {
            evSrc.close()
            setScraperState('error')
            setScraperError(data.error)
            setLogLines(prev => [...prev, `ERROR: ${data.error}`])
          }
        } catch {}
      }

      evSrc.onerror = () => {
        evSrc.close()
        setScraperState(prev => prev === 'running' ? 'done' : prev)
        fetchHistory()
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setScraperState('error')
      if (msg.includes('409') || msg.includes('corriendo') || msg.includes('job')) {
        setScraperError('Hay un job activo bloqueando el inicio. Usá "Forzar reinicio" para cancelarlo.')
      } else {
        setScraperError(msg.length < 200 ? msg : 'Error al iniciar el scraper.')
      }
      setLogLines(prev => [...prev, `Error: ${msg.slice(0, 120)}`])
    }
  }

  const startEnrichment = async () => {
    setEnrichState('running')
    setEnrichError('')
    setEnrichProgress(0)
    setEnrichFound(0)
    setEnrichTotal(0)
    setEnrichStartedAt(new Date())

    try {
      const res = await runEnrichment()
      const jobId = res?.job_id
      if (jobId) setEnrichJobId(String(jobId))

      if (enrichIntervalRef.current) clearInterval(enrichIntervalRef.current)
      enrichIntervalRef.current = setInterval(async () => {
        const data = await getScraperHistory()
        const jobs: ScraperJob[] = data.items ?? data ?? []
        const enrichJob = jobId
          ? jobs.find(j => String(j.id) === String(jobId))
          : jobs.find(j => j.tipo === 'enrichment')

        if (enrichJob) {
          setEnrichProgress(enrichJob.progress ?? 0)
          setEnrichFound(enrichJob.nuevos_agregados ?? 0)
          setEnrichTotal(enrichJob.total_encontrados ?? 0)
          setHistory(jobs)
          if (enrichJob.estado === 'completado' || enrichJob.estado === 'error') {
            clearInterval(enrichIntervalRef.current!)
            enrichIntervalRef.current = null
            setEnrichState(enrichJob.estado === 'completado' ? 'done' : 'error')
            if (enrichJob.estado === 'error') setEnrichError(enrichJob.error ?? 'Error desconocido')
          }
        }
      }, 4000)

      setTimeout(() => {
        if (enrichIntervalRef.current) {
          clearInterval(enrichIntervalRef.current)
          enrichIntervalRef.current = null
          setEnrichState(prev => prev === 'running' ? 'done' : prev)
          fetchHistory()
        }
      }, 900000)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setEnrichState('error')
      if (msg.includes('409') || msg.includes('corriendo') || msg.includes('job')) {
        setEnrichError('Hay un job activo bloqueando el inicio. Usá "Forzar reinicio" para cancelarlo.')
      } else {
        setEnrichError(msg.length < 200 ? msg : 'Error al iniciar el enriquecimiento.')
      }
    }
  }

  const errorJobs = history.filter(j => j.estado === 'error')
  const activeJobsInHistory = history.filter(j => j.estado === 'corriendo' || j.estado === 'pendiente')

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Scraper de Leads</h1>
          <p className="text-slate-500 mt-1">Extrae y enriquece leads automáticamente</p>
        </div>

        {/* Force reset button — shown when there are stuck jobs or errors blocking new starts */}
        {(activeJobsInHistory.length > 0 || scraperState === 'error' || enrichState === 'error') && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" size="sm" className="gap-2 border-orange-300 text-orange-700 hover:bg-orange-50" disabled={resetting}>
                {resetting ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                Forzar reinicio
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>¿Cancelar todos los jobs activos?</AlertDialogTitle>
                <AlertDialogDescription>
                  Esto cancela forzosamente {activeJobsInHistory.length} job(s) corriendo o pendientes y resetea el estado del scraper. Los datos ya extraídos se conservan.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Volver</AlertDialogCancel>
                <AlertDialogAction onClick={handleReset} className="bg-orange-600 hover:bg-orange-700">
                  Sí, cancelar y reiniciar
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </div>

      {/* Action Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                <p className="text-sm text-slate-500 mt-1">Busca nuevos comercios en Google Places</p>
              </div>
              {scraperError && (
                <div className="flex items-start gap-2 text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg text-left">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>{scraperError}</span>
                </div>
              )}
              <Button
                onClick={startScraper}
                disabled={anyJobRunning}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white gap-2"
                size="lg"
              >
                {isScraperRunning
                  ? <><Loader2 className="w-5 h-5 animate-spin" />Corriendo...</>
                  : <><Play className="w-5 h-5" />Ejecutar Scraper</>}
              </Button>
              {isScraperRunning && scraperJobId && (
                <Button
                  variant="outline" size="sm"
                  className="w-full border-red-300 text-red-600 hover:bg-red-50 gap-2"
                  onClick={() => stopCurrentJob(scraperJobId, () => {
                    setScraperState('idle')
                    setScraperJobId(null)
                    eventSourceRef.current?.close()
                  })}
                >
                  <StopCircle className="w-4 h-4" />
                  Pausar scraper
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
                <div className="flex items-start gap-2 text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg text-left">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>{enrichError}</span>
                </div>
              )}
              <Button
                onClick={startEnrichment}
                disabled={anyJobRunning}
                variant="outline"
                className="w-full border-blue-300 text-blue-700 hover:bg-blue-50 gap-2"
                size="lg"
              >
                {isEnrichRunning
                  ? <><Loader2 className="w-5 h-5 animate-spin" />Enriqueciendo...</>
                  : <><RefreshCw className="w-5 h-5" />Enriquecer Leads</>}
              </Button>
              {isEnrichRunning && enrichJobId && (
                <Button
                  variant="outline" size="sm"
                  className="w-full border-red-300 text-red-600 hover:bg-red-50 gap-2"
                  onClick={() => stopCurrentJob(enrichJobId, () => {
                    setEnrichState('idle')
                    setEnrichJobId(null)
                    if (enrichIntervalRef.current) { clearInterval(enrichIntervalRef.current); enrichIntervalRef.current = null }
                  })}
                >
                  <StopCircle className="w-4 h-4" />
                  Pausar enriquecimiento
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

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
                    <span className="font-semibold">{progress}%</span>
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
                <div key={i} className={line.startsWith('ERROR') || line.startsWith('Error') ? 'text-red-400' : line.startsWith('✓') ? 'text-emerald-400' : 'text-slate-300'}>
                  {line}
                </div>
              ))}
            </div>
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
            <div className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-slate-600">Progreso</span>
                <span className="font-semibold">{enrichProgress}%</span>
              </div>
              <Progress value={enrichProgress} className="h-3" />
            </div>
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
                  {enrichStartedAt ? formatDistanceToNow(enrichStartedAt, { locale: es }) : '—'}
                </p>
              </div>
            </div>
            {isEnrichRunning && (
              <p className="text-xs text-slate-400 text-center">
                Actualizando cada 4 segundos · El proceso puede tomar varios minutos
              </p>
            )}
            {enrichState === 'done' && (
              <p className="text-sm text-emerald-700 font-medium text-center">
                ✓ {enrichFound} lead{enrichFound !== 1 ? 's' : ''} enriquecido{enrichFound !== 1 ? 's' : ''} de {enrichTotal} procesados
              </p>
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
          <div className="flex items-center justify-between gap-3">
            <CardTitle className="text-base">
              Historial de Jobs
              {hasActiveJobs && (
                <Badge variant="warning" className="ml-2 gap-1 text-xs">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  {activeJobsInHistory.length} activo{activeJobsInHistory.length !== 1 ? 's' : ''}
                </Badge>
              )}
            </CardTitle>
            <div className="flex items-center gap-2">
              {errorJobs.length > 0 && (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="ghost" size="sm" className="gap-1.5 text-red-600 hover:text-red-700 hover:bg-red-50 text-xs h-8">
                      <Trash2 className="w-3.5 h-3.5" />
                      Limpiar {errorJobs.length} error{errorJobs.length !== 1 ? 'es' : ''}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>¿Eliminar todos los jobs con error?</AlertDialogTitle>
                      <AlertDialogDescription>
                        Se eliminarán {errorJobs.length} job(s) con error del historial. Esta acción no se puede deshacer.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancelar</AlertDialogCancel>
                      <AlertDialogAction
                        className="bg-red-600 hover:bg-red-700"
                        onClick={async () => {
                          for (const job of errorJobs) {
                            try { await deleteScraperJob(job.id) } catch {}
                          }
                          setHistory(prev => prev.filter(j => j.estado !== 'error'))
                        }}
                      >
                        Eliminar todos
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
              <Button
                variant="outline" size="sm"
                onClick={() => fetchHistory()}
                disabled={refreshing}
                className="gap-1.5 h-8 text-xs"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                {refreshing ? 'Actualizando...' : 'Actualizar'}
              </Button>
            </div>
          </div>
          {historyError && (
            <p className="text-xs text-red-500 mt-1 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              {historyError}
            </p>
          )}
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
                    <TableHead>Inicio</TableHead>
                    <TableHead>Fin</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead>Progreso</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead className="text-right">Nuevos</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((job) => (
                    <TableRow key={job.id} className={job.estado === 'error' ? 'bg-red-50/40' : job.estado === 'corriendo' ? 'bg-emerald-50/30' : ''}>
                      <TableCell>
                        <Badge variant={job.tipo === 'enrichment' ? 'secondary' : 'warning'} className="text-xs capitalize">
                          {job.tipo === 'enrichment' ? 'Enriquec.' : 'Scraper'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-slate-600 text-sm">{formatDate(job.started_at)}</TableCell>
                      <TableCell className="text-slate-600 text-sm">{formatDate(job.finished_at)}</TableCell>
                      <TableCell>
                        <div className="space-y-0.5">
                          <JobStatusBadge estado={job.estado} />
                          {job.error && (
                            <p className="text-xs text-red-500 max-w-[180px] truncate" title={job.error}>
                              {job.error}
                            </p>
                          )}
                        </div>
                      </TableCell>
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
                      <TableCell className="text-right font-medium">{job.total_encontrados?.toLocaleString('es-AR') ?? '—'}</TableCell>
                      <TableCell className="text-right">
                        {job.nuevos_agregados !== undefined
                          ? <span className="text-emerald-700 font-semibold">+{job.nuevos_agregados.toLocaleString('es-AR')}</span>
                          : '—'}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1 justify-end">
                          {(job.estado === 'corriendo' || job.estado === 'pendiente') && (
                            <Button
                              variant="ghost" size="sm"
                              onClick={() => cancelJob(job.id)}
                              disabled={cancellingId === job.id}
                              className="text-orange-500 hover:text-orange-700 hover:bg-orange-50 h-7 w-7 p-0"
                              title="Cancelar / pausar job"
                            >
                              {cancellingId === job.id
                                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                : <StopCircle className="w-3.5 h-3.5" />}
                            </Button>
                          )}
                          {(job.estado === 'error' || job.estado === 'completado') && (
                            <Button
                              variant="ghost" size="sm"
                              onClick={() => deleteJob(job.id)}
                              disabled={deletingId === job.id}
                              className="text-slate-400 hover:text-red-600 hover:bg-red-50 h-7 w-7 p-0"
                              title="Eliminar del historial"
                            >
                              {deletingId === job.id
                                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                : <Trash2 className="w-3.5 h-3.5" />}
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
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

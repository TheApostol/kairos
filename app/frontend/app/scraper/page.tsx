'use client'

import { useEffect, useState, useRef } from 'react'
import { getScraperHistory, runScraper, runEnrichment, getApiUrl } from '@/lib/api'
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
import { Play, RefreshCw, Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

interface ScraperJob {
  id: number
  started_at?: string
  finished_at?: string
  estado: string
  total_encontrados?: number
  nuevos_agregados?: number
  error?: string
}

type RunState = 'idle' | 'running' | 'done' | 'error'

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
      <Icon className="w-3 h-3" />
      {estado}
    </Badge>
  )
}

export default function ScraperPage() {
  const [history, setHistory] = useState<ScraperJob[]>([])
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [scraperState, setScraperState] = useState<RunState>('idle')
  const [enrichState, setEnrichState] = useState<RunState>('idle')
  const [progress, setProgress] = useState(0)
  const [currentQuery, setCurrentQuery] = useState('')
  const [logLines, setLogLines] = useState<string[]>([])
  const logRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  const [refreshing, setRefreshing] = useState(false)

  const fetchHistory = async () => {
    setRefreshing(true)
    try {
      const data = await getScraperHistory()
      setHistory(data.items ?? data ?? [])
    } catch {}
    finally { setRefreshing(false) }
  }

  useEffect(() => {
    fetchHistory().finally(() => setLoadingHistory(false))
    return () => {
      eventSourceRef.current?.close()
    }
  }, [])

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logLines])

  const startScraper = async () => {
    setScraperState('running')
    setProgress(0)
    setCurrentQuery('')
    setLogLines(['Iniciando scraper...'])

    try {
      await runScraper()

      // Connect to SSE stream
      const es = new EventSource(getApiUrl('/scraper/progress'))
      eventSourceRef.current = es

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.progress !== undefined) setProgress(Math.min(100, data.progress))
          if (data.query) {
            setCurrentQuery(data.query)
            setLogLines((prev) => [...prev.slice(-49), `[${new Date().toLocaleTimeString('es-AR')}] ${data.query}`])
          }
          if (data.done || data.progress >= 100) {
            es.close()
            setScraperState('done')
            setProgress(100)
            setCurrentQuery('Completado')
            fetchHistory()
          }
          if (data.error) {
            es.close()
            setScraperState('error')
            setLogLines((prev) => [...prev, `ERROR: ${data.error}`])
          }
        } catch {}
      }

      es.onerror = () => {
        es.close()
        // If SSE ends without explicit done, check if it's actually completed
        setScraperState((prev) => prev === 'running' ? 'done' : prev)
        fetchHistory()
      }
    } catch {
      setScraperState('error')
      setLogLines((prev) => [...prev, 'Error al iniciar el scraper'])
    }
  }

  const startEnrichment = async () => {
    setEnrichState('running')
    try {
      await runEnrichment()
      // Backend runs as background job — poll history every 5s until done
      const interval = setInterval(async () => {
        const data = await getScraperHistory()
        const jobs = data.items ?? data ?? []
        const latest = jobs[0]
        if (latest && (latest.estado === 'completado' || latest.estado === 'error')) {
          clearInterval(interval)
          setEnrichState(latest.estado === 'completado' ? 'done' : 'error')
          setHistory(jobs)
        }
      }, 5000)
      // Safety: stop polling after 10 minutes
      setTimeout(() => { clearInterval(interval); setEnrichState('done') }, 600000)
    } catch {
      setEnrichState('error')
    }
  }

  const isScraperRunning = scraperState === 'running'
  const isEnrichRunning = enrichState === 'running'

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Scraper de Leads</h1>
        <p className="text-slate-500 mt-1">Extrae y enriquece leads automáticamente</p>
      </div>

      {/* Action Buttons */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                <p className="text-sm text-slate-500 mt-1">
                  Busca nuevos leads en directorios y webs
                </p>
              </div>
              <Button
                onClick={startScraper}
                disabled={isScraperRunning}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white gap-2"
                size="lg"
              >
                {isScraperRunning ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Corriendo...
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    Ejecutar Scraper
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

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
                <p className="text-sm text-slate-500 mt-1">
                  Extrae emails y teléfonos de websites
                </p>
              </div>
              <Button
                onClick={startEnrichment}
                disabled={isEnrichRunning}
                variant="outline"
                className="w-full border-blue-300 text-blue-700 hover:bg-blue-50 gap-2"
                size="lg"
              >
                {isEnrichRunning ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Enriqueciendo...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-5 h-5" />
                    Enriquecer Leads
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Progress Panel */}
      {(isScraperRunning || scraperState === 'done' || scraperState === 'error') && logLines.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">
                {isScraperRunning ? 'Scraper en ejecución' : scraperState === 'done' ? 'Scraper completado' : 'Error en scraper'}
              </CardTitle>
              {isScraperRunning && (
                <Badge variant="warning" className="gap-1">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Corriendo
                </Badge>
              )}
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

            <div
              ref={logRef}
              className="bg-slate-900 rounded-lg p-4 h-40 overflow-y-auto font-mono text-xs"
            >
              {logLines.map((line, i) => (
                <div
                  key={i}
                  className={`${
                    line.startsWith('ERROR') ? 'text-red-400' : 
                    line.startsWith('Completado') ? 'text-emerald-400' : 
                    'text-slate-300'
                  }`}
                >
                  {line}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Enrichment status */}
      {(isEnrichRunning || enrichState === 'done' || enrichState === 'error') && (
        <Card>
          <CardContent className="pt-4 flex items-center gap-3">
            {isEnrichRunning && <Loader2 className="w-5 h-5 animate-spin text-blue-600" />}
            {enrichState === 'done' && <CheckCircle2 className="w-5 h-5 text-emerald-600" />}
            {enrichState === 'error' && <XCircle className="w-5 h-5 text-red-600" />}
            <p className="text-sm text-slate-700">
              {isEnrichRunning && 'Enriqueciendo leads... Esto puede tomar varios minutos.'}
              {enrichState === 'done' && 'Enriquecimiento completado exitosamente.'}
              {enrichState === 'error' && 'Error al enriquecer leads. Intentá de nuevo.'}
            </p>
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
            <Table className="min-w-[560px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Inicio</TableHead>
                  <TableHead>Fin</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Nuevos</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="text-slate-600">{formatDate(job.started_at)}</TableCell>
                    <TableCell className="text-slate-600">{formatDate(job.finished_at)}</TableCell>
                    <TableCell><JobStatusBadge estado={job.estado} /></TableCell>
                    <TableCell className="font-medium">{job.total_encontrados?.toLocaleString('es-AR') ?? '—'}</TableCell>
                    <TableCell>
                      {job.nuevos_agregados !== undefined ? (
                        <span className="text-emerald-700 font-semibold">
                          +{job.nuevos_agregados.toLocaleString('es-AR')}
                        </span>
                      ) : '—'}
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

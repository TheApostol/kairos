'use client'

import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { getApiUrl } from '@/lib/api'

interface ScraperStatus {
  isRunning: boolean
  progress: number
  currentQuery: string
  jobType: 'scraper' | 'enrichment' | null
}

const ScraperStatusContext = createContext<ScraperStatus>({
  isRunning: false,
  progress: 0,
  currentQuery: '',
  jobType: null,
})

export function useScraperStatus() {
  return useContext(ScraperStatusContext)
}

export function ScraperStatusProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<ScraperStatus>({
    isRunning: false,
    progress: 0,
    currentQuery: '',
    jobType: null,
  })
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const keepaliveRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    let mounted = true

    // Keepalive: ping /scraper/history every 30s to prevent Render free-tier
    // spindown (process dies after 15 min with no HTTP requests, killing the
    // background scraper/enricher thread). Also syncs job state from DB so the
    // banner stays accurate even when the SSE briefly disconnects.
    keepaliveRef.current = setInterval(async () => {
      if (!mounted) return
      try {
        const res = await fetch(getApiUrl('/scraper/history'))
        if (!res.ok) return
        const data = await res.json()
        const jobs: Array<{ estado: string; progress?: number; tipo?: string }> = data.items ?? []
        const running = jobs.find((j) => j.estado === 'corriendo' || j.estado === 'pendiente')
        if (running) {
          setStatus((prev) => ({
            ...prev,
            isRunning: true,
            progress: running.progress ?? prev.progress,
            jobType: running.tipo === 'enrichment' ? 'enrichment' : 'scraper',
          }))
        }
      } catch {}
    }, 30_000)

    const connect = () => {
      if (!mounted) return
      esRef.current?.close()

      const es = new EventSource(getApiUrl('/scraper/progress'))
      esRef.current = es

      es.onmessage = (event) => {
        if (!mounted) return
        try {
          const data = JSON.parse(event.data)
          if (data.done || data.error) {
            setStatus({ isRunning: false, progress: 100, currentQuery: '', jobType: null })
            es.close()
            timerRef.current = setTimeout(connect, 5000)
          } else {
            setStatus((prev) => ({
              isRunning: true,
              progress: data.progress ?? 0,
              currentQuery: data.query ?? prev.currentQuery,
              jobType: prev.jobType,
            }))
          }
        } catch {}
      }

      es.onerror = () => {
        if (!mounted) return
        es.close()
        setStatus((prev) => ({ ...prev, isRunning: false }))
        timerRef.current = setTimeout(connect, 5000)
      }
    }

    connect()

    return () => {
      mounted = false
      esRef.current?.close()
      if (timerRef.current) clearTimeout(timerRef.current)
      if (keepaliveRef.current) clearInterval(keepaliveRef.current)
    }
  }, [])

  return (
    <ScraperStatusContext.Provider value={status}>
      {children}
    </ScraperStatusContext.Provider>
  )
}

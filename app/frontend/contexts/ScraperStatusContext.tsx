'use client'

import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { getApiUrl } from '@/lib/api'

interface ScraperStatus {
  isRunning: boolean
  progress: number
  currentQuery: string
}

const ScraperStatusContext = createContext<ScraperStatus>({
  isRunning: false,
  progress: 0,
  currentQuery: '',
})

export function useScraperStatus() {
  return useContext(ScraperStatusContext)
}

export function ScraperStatusProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<ScraperStatus>({
    isRunning: false,
    progress: 0,
    currentQuery: '',
  })
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    let mounted = true

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
            setStatus({ isRunning: false, progress: 100, currentQuery: '' })
            es.close()
            timerRef.current = setTimeout(connect, 15000)
          } else {
            setStatus({
              isRunning: true,
              progress: data.progress ?? 0,
              currentQuery: data.query ?? '',
            })
          }
        } catch {}
      }

      es.onerror = () => {
        if (!mounted) return
        es.close()
        setStatus((prev) => ({ ...prev, isRunning: false }))
        timerRef.current = setTimeout(connect, 15000)
      }
    }

    connect()

    return () => {
      mounted = false
      esRef.current?.close()
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  return (
    <ScraperStatusContext.Provider value={status}>
      {children}
    </ScraperStatusContext.Provider>
  )
}

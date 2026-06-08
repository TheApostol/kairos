'use client'

import { usePathname, useRouter } from 'next/navigation'
import { useScraperStatus } from '@/contexts/ScraperStatusContext'
import { Loader2 } from 'lucide-react'

export default function ScraperBanner() {
  const { isRunning, progress, currentQuery } = useScraperStatus()
  const pathname = usePathname()
  const router = useRouter()

  if (!isRunning || pathname === '/scraper') return null

  return (
    <div
      onClick={() => router.push('/scraper')}
      className="fixed bottom-4 right-4 z-50 cursor-pointer w-72 rounded-xl shadow-xl border border-emerald-200 bg-white overflow-hidden"
    >
      <div className="px-4 py-3 flex items-center gap-3">
        <Loader2 className="w-4 h-4 text-emerald-600 animate-spin flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-slate-800">Scraper corriendo — {progress}%</p>
          {currentQuery && (
            <p className="text-xs text-slate-500 truncate mt-0.5">{currentQuery}</p>
          )}
        </div>
      </div>
      {/* Progress bar */}
      <div className="h-1 bg-slate-100">
        <div
          className="h-1 bg-emerald-500 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}

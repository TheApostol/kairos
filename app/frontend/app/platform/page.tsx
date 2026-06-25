'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { getPlatformSummary } from '@/lib/api'

type Summary = Record<string, unknown>

function formatValue(value: unknown) {
  if (typeof value === 'number') return value.toLocaleString()
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (value && typeof value === 'object') return JSON.stringify(value)
  return String(value ?? '-')
}

export default function PlatformOverviewPage() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getPlatformSummary()
      .then(setSummary)
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load platform summary'))
  }, [])

  if (!summary && !error) {
    return <div className="flex justify-center py-24"><Loader2 className="h-6 w-6 animate-spin text-amber-300" /></div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Platform Overview</h1>
        <p className="mt-1 text-sm text-slate-400">Operational snapshot across Polkorp tenants.</p>
      </div>
      {error && <p className="rounded-md border border-red-900 bg-red-950 px-4 py-3 text-sm text-red-200">{error}</p>}
      {summary && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Object.entries(summary).map(([key, value]) => (
            <div key={key} className="rounded-md border border-slate-800 bg-slate-900 p-4">
              <p className="text-xs uppercase text-slate-500">{key.replaceAll('_', ' ')}</p>
              <p className="mt-2 break-words text-lg font-semibold text-white">{formatValue(value)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

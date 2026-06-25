'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { getPlatformUsage } from '@/lib/api'

interface UsageEvent {
  id?: string
  organization_id?: string
  metric?: string
  quantity?: number
  source?: string
  created_at?: string
}

export default function PlatformUsagePage() {
  const [items, setItems] = useState<UsageEvent[]>([])
  const [totals, setTotals] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getPlatformUsage({ days: 30, limit: 500 })
      .then((data) => {
        setItems(data.items ?? [])
        setTotals(data.totals ?? {})
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load usage'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-white">Usage</h1>
        <p className="mt-1 text-sm text-slate-400">Last 30 days of metered SaaS activity.</p>
      </div>
      {loading ? <Loader2 className="h-6 w-6 animate-spin text-amber-300" /> : error ? (
        <p className="rounded-md border border-red-900 bg-red-950 px-4 py-3 text-sm text-red-200">{error}</p>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(totals).map(([metric, quantity]) => (
              <div key={metric} className="rounded-md border border-slate-800 bg-slate-900 p-4">
                <p className="text-xs uppercase text-slate-500">{metric}</p>
                <p className="mt-2 text-xl font-semibold text-white">{quantity.toLocaleString()}</p>
              </div>
            ))}
          </div>
          <div className="overflow-hidden rounded-md border border-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-900 text-xs uppercase text-slate-500">
                <tr><th className="px-4 py-3">Metric</th><th className="px-4 py-3">Qty</th><th className="px-4 py-3">Source</th><th className="px-4 py-3">Organization</th><th className="px-4 py-3">Created</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {items.map((event, idx) => (
                  <tr key={event.id ?? idx}>
                    <td className="px-4 py-3 text-white">{event.metric ?? '-'}</td>
                    <td className="px-4 py-3 text-slate-300">{event.quantity ?? 0}</td>
                    <td className="px-4 py-3 text-slate-300">{event.source ?? '-'}</td>
                    <td className="px-4 py-3 text-slate-400">{event.organization_id ?? '-'}</td>
                    <td className="px-4 py-3 text-slate-400">{event.created_at?.slice(0, 19) ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

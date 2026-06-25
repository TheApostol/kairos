'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { getPlatformPlans, updatePlatformPlanLimit } from '@/lib/api'

interface PlanLimit {
  id?: string
  metric?: string
  limit_value?: number
  period?: string
}

interface Plan {
  id: string
  name?: string
  monthly_price_cents?: number
  currency?: string
  active?: boolean
  limits?: PlanLimit[]
}

export default function PlatformPlansPage() {
  const [items, setItems] = useState<Plan[]>([])
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getPlatformPlans()
      setItems(data.items ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load plans')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const updateLimit = async (limit: PlanLimit, data: Record<string, unknown>) => {
    if (!limit.id) return
    setSavingId(limit.id)
    setError(null)
    try {
      await updatePlatformPlanLimit(limit.id, data)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update plan limit')
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-white">Plans</h1>
        <p className="mt-1 text-sm text-slate-400">Starter, Growth, Pro, and Enterprise packaging.</p>
      </div>
      {loading ? <Loader2 className="h-6 w-6 animate-spin text-amber-300" /> : error ? (
        <p className="rounded-md border border-red-900 bg-red-950 px-4 py-3 text-sm text-red-200">{error}</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {items.map((plan) => (
            <div key={plan.id} className="rounded-md border border-slate-800 bg-slate-900 p-4">
              <div className="flex items-center justify-between gap-2">
                <h2 className="font-semibold text-white">{plan.name ?? plan.id}</h2>
                <span className="text-xs text-slate-400">{plan.active === false ? 'Inactive' : 'Active'}</span>
              </div>
              <p className="mt-3 text-2xl font-semibold text-amber-300">
                {((plan.monthly_price_cents ?? 0) / 100).toLocaleString(undefined, { style: 'currency', currency: plan.currency ?? 'USD' })}
              </p>
              <div className="mt-4 space-y-1">
                {(plan.limits ?? []).map((limit) => (
                  <div key={limit.id ?? `${limit.metric}-${limit.period}`} className="grid grid-cols-[1fr_88px] items-center gap-2 text-xs text-slate-300">
                    <span>{limit.metric} / {limit.period}</span>
                    <input
                      type="number"
                      defaultValue={limit.limit_value ?? 0}
                      disabled={savingId === limit.id}
                      onBlur={(e) => {
                        const nextValue = Number(e.target.value)
                        if (nextValue !== limit.limit_value) updateLimit(limit, { limit_value: nextValue })
                      }}
                      className="h-8 rounded border border-slate-700 bg-slate-950 px-2 text-right text-slate-100"
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { getPlatformPlans, getPlatformSubscriptions, updatePlatformSubscription } from '@/lib/api'

interface Subscription {
  id: string
  organization_id?: string
  plan_id?: string
  status?: string
  provider?: string
  current_period_end?: string
}

interface Plan {
  id: string
  name?: string
}

export default function PlatformSubscriptionsPage() {
  const [items, setItems] = useState<Subscription[]>([])
  const [plans, setPlans] = useState<Plan[]>([])
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [subscriptionsData, plansData] = await Promise.all([
        getPlatformSubscriptions({ limit: 200 }),
        getPlatformPlans(),
      ])
      setItems(subscriptionsData.items ?? [])
      setPlans(plansData.items ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load subscriptions')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const updateSubscription = async (sub: Subscription, data: Record<string, unknown>) => {
    setSavingId(sub.id)
    setError(null)
    try {
      await updatePlatformSubscription(sub.id, data)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update subscription')
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-white">Subscriptions</h1>
        <p className="mt-1 text-sm text-slate-400">Billing state by tenant.</p>
      </div>
      {loading ? <Loader2 className="h-6 w-6 animate-spin text-amber-300" /> : error ? (
        <p className="rounded-md border border-red-900 bg-red-950 px-4 py-3 text-sm text-red-200">{error}</p>
      ) : (
        <div className="grid gap-3">
          {items.map((sub) => (
            <div key={sub.id} className="rounded-md border border-slate-800 bg-slate-900 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <select
                  value={sub.plan_id ?? ''}
                  disabled={savingId === sub.id}
                  onChange={(e) => updateSubscription(sub, { plan_id: e.target.value })}
                  className="h-8 rounded border border-slate-700 bg-slate-950 px-2 text-sm font-medium text-white"
                >
                  {plans.map((plan) => <option key={plan.id} value={plan.id}>{plan.name ?? plan.id}</option>)}
                </select>
                <select
                  value={sub.status ?? 'trialing'}
                  disabled={savingId === sub.id}
                  onChange={(e) => updateSubscription(sub, { status: e.target.value })}
                  className="h-8 rounded border border-slate-700 bg-slate-950 px-2 text-xs text-slate-100"
                >
                  {['trialing', 'active', 'past_due', 'cancelled', 'paused'].map((status) => <option key={status} value={status}>{status}</option>)}
                </select>
              </div>
              <p className="mt-2 text-xs text-slate-400">Org: {sub.organization_id ?? '-'}</p>
              <p className="mt-1 text-xs text-slate-400">Provider: {sub.provider ?? 'manual'} · Ends: {sub.current_period_end?.slice(0, 10) ?? '-'}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

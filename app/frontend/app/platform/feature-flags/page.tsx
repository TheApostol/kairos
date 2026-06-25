'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { getPlatformFeatureFlags, updatePlatformFeatureFlag } from '@/lib/api'

interface FlagOrg {
  id: string
  name?: string
  slug?: string
  status?: string
  customer_tier?: string
  feature_flags?: Record<string, unknown>
}

export default function PlatformFeatureFlagsPage() {
  const [items, setItems] = useState<FlagOrg[]>([])
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [flagKey, setFlagKey] = useState('lead_client')
  const [flagValue, setFlagValue] = useState('true')

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getPlatformFeatureFlags({ limit: 200 })
      setItems(data.items ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load feature flags')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const parseFlagValue = () => {
    try {
      return JSON.parse(flagValue)
    } catch {
      return flagValue
    }
  }

  const updateFlag = async (org: FlagOrg) => {
    if (!flagKey.trim()) return
    setSavingId(org.id)
    setError(null)
    try {
      await updatePlatformFeatureFlag(org.id, { key: flagKey.trim(), value: parseFlagValue() })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update feature flag')
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-white">Feature Flags</h1>
        <p className="mt-1 text-sm text-slate-400">Organization-level rollout flags.</p>
      </div>
      {loading ? <Loader2 className="h-6 w-6 animate-spin text-amber-300" /> : error ? (
        <p className="rounded-md border border-red-900 bg-red-950 px-4 py-3 text-sm text-red-200">{error}</p>
      ) : (
        <div className="grid gap-3">
          <div className="grid gap-2 rounded-md border border-slate-800 bg-slate-900 p-4 sm:grid-cols-[1fr_1fr]">
            <input value={flagKey} onChange={(e) => setFlagKey(e.target.value)} className="h-9 rounded border border-slate-700 bg-slate-950 px-3 text-sm text-white" placeholder="flag_key" />
            <input value={flagValue} onChange={(e) => setFlagValue(e.target.value)} className="h-9 rounded border border-slate-700 bg-slate-950 px-3 text-sm text-white" placeholder="true, false, string, or JSON" />
          </div>
          {items.map((org) => (
            <div key={org.id} className="rounded-md border border-slate-800 bg-slate-900 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium text-white">{org.name ?? org.slug ?? org.id}</p>
                  <p className="text-xs text-slate-500">{org.customer_tier ?? 'standard'} · {org.status ?? '-'}</p>
                </div>
                <button
                  disabled={savingId === org.id}
                  onClick={() => updateFlag(org)}
                  className="rounded border border-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-50"
                >
                  Set Flag
                </button>
              </div>
              <pre className="mt-3 overflow-x-auto rounded bg-slate-950 p-3 text-xs text-slate-300">
                {JSON.stringify(org.feature_flags ?? {}, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

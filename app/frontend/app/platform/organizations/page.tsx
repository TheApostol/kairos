'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { getPlatformOrganizations, updatePlatformOrganization } from '@/lib/api'

interface Organization {
  id: string
  name?: string
  slug?: string
  status?: string
  plan?: string
  customer_tier?: string
  public_catalog_enabled?: boolean
  created_at?: string
}

export default function PlatformOrganizationsPage() {
  const [items, setItems] = useState<Organization[]>([])
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getPlatformOrganizations({ limit: 200 })
      setItems(data.items ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load organizations')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const updateOrg = async (org: Organization, data: Record<string, unknown>) => {
    setSavingId(org.id)
    setError(null)
    try {
      await updatePlatformOrganization(org.id, data)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update organization')
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-white">Organizations</h1>
        <p className="mt-1 text-sm text-slate-400">Tenant registry and lead-client visibility.</p>
      </div>
      {loading ? <Loader2 className="h-6 w-6 animate-spin text-amber-300" /> : error ? (
        <p className="rounded-md border border-red-900 bg-red-950 px-4 py-3 text-sm text-red-200">{error}</p>
      ) : (
        <div className="overflow-hidden rounded-md border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900 text-xs uppercase text-slate-500">
              <tr><th className="px-4 py-3">Name</th><th className="px-4 py-3">Slug</th><th className="px-4 py-3">Plan</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Tier</th><th className="px-4 py-3">Catalog</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {items.map((org) => (
                <tr key={org.id} className="bg-slate-950">
                  <td className="px-4 py-3 font-medium text-white">{org.name ?? org.id}</td>
                  <td className="px-4 py-3 text-slate-300">{org.slug ?? '-'}</td>
                  <td className="px-4 py-3 text-slate-300">{org.plan ?? '-'}</td>
                  <td className="px-4 py-3">
                    <select
                      value={org.status ?? 'active'}
                      disabled={savingId === org.id}
                      onChange={(e) => updateOrg(org, { status: e.target.value })}
                      className="h-8 rounded border border-slate-700 bg-slate-900 px-2 text-xs text-slate-100"
                    >
                      {['active', 'trialing', 'past_due', 'cancelled', 'suspended'].map((status) => <option key={status} value={status}>{status}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={org.customer_tier ?? 'standard'}
                      disabled={savingId === org.id}
                      onChange={(e) => updateOrg(org, { customer_tier: e.target.value })}
                      className="h-8 rounded border border-slate-700 bg-slate-900 px-2 text-xs text-slate-100"
                    >
                      {['lead_client', 'standard', 'strategic', 'enterprise'].map((tier) => <option key={tier} value={tier}>{tier}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      disabled={savingId === org.id}
                      onClick={() => updateOrg(org, { public_catalog_enabled: !org.public_catalog_enabled })}
                      className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-50"
                    >
                      {org.public_catalog_enabled === false ? 'Disabled' : 'Enabled'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

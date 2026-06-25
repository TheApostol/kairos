'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { getPlatformAuditLogs } from '@/lib/api'

interface AuditLog {
  id?: string
  organization_id?: string
  actor_email?: string
  actor_role?: string
  action?: string
  entity?: string
  entity_id?: string
  created_at?: string
}

export default function PlatformAuditLogsPage() {
  const [items, setItems] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getPlatformAuditLogs({ limit: 200 })
      .then((data) => setItems(data.items ?? []))
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load audit logs'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-white">Audit Logs</h1>
        <p className="mt-1 text-sm text-slate-400">Sensitive tenant and platform actions.</p>
      </div>
      {loading ? <Loader2 className="h-6 w-6 animate-spin text-amber-300" /> : error ? (
        <p className="rounded-md border border-red-900 bg-red-950 px-4 py-3 text-sm text-red-200">{error}</p>
      ) : (
        <div className="grid gap-2">
          {items.map((log, idx) => (
            <div key={log.id ?? idx} className="rounded-md border border-slate-800 bg-slate-900 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium text-white">{log.action ?? '-'}</p>
                <span className="text-xs text-slate-500">{log.created_at?.slice(0, 19) ?? '-'}</span>
              </div>
              <p className="mt-2 text-xs text-slate-400">
                {log.actor_email ?? 'system'} · {log.actor_role ?? '-'} · {log.entity ?? '-'} {log.entity_id ?? ''}
              </p>
              <p className="mt-1 text-xs text-slate-500">Org: {log.organization_id ?? '-'}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { PolkorpBrandMark, PolkorpWordmark } from '@/components/PolkorpBrand'
import { getPlatformLeadClient, getPlatformOrganizations, getPlatformSummary } from '@/lib/platformApi'

export default function AdminDashboardPage() {
  const [summary, setSummary] = useState<any>(null)
  const [organizations, setOrganizations] = useState<any[]>([])
  const [leadClient, setLeadClient] = useState<any>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      getPlatformSummary(),
      getPlatformOrganizations({ limit: 20 }),
      getPlatformLeadClient(),
    ])
      .then(([summaryData, orgData, leadData]) => {
        setSummary(summaryData)
        setOrganizations(orgData.items ?? [])
        setLeadClient(leadData.primary)
      })
      .catch((err) => setError(err.message || 'No se pudo cargar el panel'))
  }, [])

  return (
    <main className="min-h-screen bg-[#050914] text-[#F5F7FA]">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_12%_8%,rgba(47,168,255,0.18),transparent_30%),radial-gradient(circle_at_86%_18%,rgba(11,95,255,0.14),transparent_28%),linear-gradient(180deg,rgba(10,15,26,0),rgba(10,15,26,0.82))]" />
      <div className="mx-auto max-w-7xl px-6 py-8">
        <header className="relative mb-8 flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-4">
            <PolkorpBrandMark size="md" />
            <div>
              <PolkorpWordmark />
              <h1 className="mt-4 text-4xl font-black tracking-tight text-[#F5F7FA]">Polkorp Suite</h1>
              <p className="mt-2 max-w-2xl text-[#C9CED6]">Control global de tenants, billing, uso, auditoría y clientes SaaS.</p>
            </div>
          </div>
          <div className="flex gap-3">
            <Link href="/admin/organizations/new" className="rounded-xl bg-[#0B5FFF] px-4 py-3 font-bold text-white shadow-[0_14px_40px_rgba(11,95,255,0.28)] transition hover:bg-[#084ED6]">Crear organización</Link>
            <Link href="/admin/products/check" className="rounded-xl border border-white/15 px-4 py-3 font-bold text-[#F5F7FA] transition hover:border-[#2FA8FF]/60 hover:text-[#2FA8FF]">SKU / imágenes</Link>
          </div>
        </header>

        {error && <div className="relative mb-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">{error}</div>}

        <section className="relative grid gap-4 md:grid-cols-4">
          <Kpi label="Organizaciones" value={summary?.organizations_total ?? '—'} />
          <Kpi label="Activas" value={summary?.organizations_active ?? '—'} />
          <Kpi label="Trials" value={summary?.organizations_trialing ?? '—'} />
          <Kpi label="Past due" value={summary?.subscriptions_past_due ?? '—'} />
        </section>

        <section className="relative mt-6 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 shadow-[0_20px_80px_rgba(0,0,0,0.18)]">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-bold">Organizaciones recientes</h2>
              <Link href="/admin/organizations/new" className="text-sm font-semibold text-[#2FA8FF]">Nueva</Link>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-[#9BA6B6]"><tr><th className="py-2">Cliente</th><th>Plan</th><th>Tier</th><th>Admin cliente</th></tr></thead>
                <tbody>
                  {organizations.map((org) => (
                    <tr key={org.id} className="border-t border-white/10">
                      <td className="py-3"><div className="font-semibold">{org.name}</div><div className="text-xs text-[#9BA6B6]">{org.slug}</div></td>
                      <td>{org.plan ?? 'starter'}</td>
                      <td>{org.customer_tier ?? 'standard'}</td>
                      <td><Link className="text-[#2FA8FF]" href={org.admin_path || `/${org.slug}/admin`}>{org.admin_path || `/${org.slug}/admin`}</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-2xl border border-[#2FA8FF]/30 bg-[#0B5FFF]/10 p-5 shadow-[0_20px_80px_rgba(11,95,255,0.12)]">
            <p className="text-xs uppercase tracking-[0.25em] text-[#2FA8FF]">Lead client</p>
            <h2 className="mt-2 text-2xl font-black">{leadClient?.name || 'Kairos'}</h2>
            <p className="mt-2 text-sm text-[#C9CED6]">Tenant de referencia para validar funcionalidades antes de replicarlas a clientes Polkorp.</p>
            <div className="mt-5 space-y-2 text-sm text-[#C9CED6]">
              <div><b>Slug:</b> {leadClient?.slug || 'kairos'}</div>
              <div><b>Plan:</b> {leadClient?.plan || 'pro'}</div>
              <div><b>Admin:</b> {leadClient?.admin_path || '/kairos/admin'}</div>
            </div>
            <Link href={leadClient?.admin_path || '/kairos/admin'} className="mt-5 inline-flex rounded-xl bg-[#2FA8FF] px-4 py-3 font-bold text-[#050914] transition hover:bg-[#75C8FF]">Abrir Kairos</Link>
          </div>
        </section>
      </div>
    </main>
  )
}

function Kpi({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
      <p className="text-sm text-[#9BA6B6]">{label}</p>
      <div className="mt-2 text-3xl font-black">{value}</div>
    </div>
  )
}

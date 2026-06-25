'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
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
    <main className="min-h-screen bg-[#07080b] text-[#f7f2e8]">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-[#c9a040]">Polkorp</p>
            <h1 className="mt-2 text-4xl font-black tracking-tight">Platform Admin</h1>
            <p className="mt-2 text-[#a79f91]">Control global de tenants, billing, uso, auditoría y clientes SaaS.</p>
          </div>
          <div className="flex gap-3">
            <Link href="/admin/organizations/new" className="rounded-xl bg-[#c9a040] px-4 py-3 font-bold text-black">Crear organización</Link>
            <Link href="/admin/products/check" className="rounded-xl border border-white/15 px-4 py-3 font-bold text-white">SKU / imágenes</Link>
          </div>
        </header>

        {error && <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">{error}</div>}

        <section className="grid gap-4 md:grid-cols-4">
          <Kpi label="Organizaciones" value={summary?.organizations_total ?? '—'} />
          <Kpi label="Activas" value={summary?.organizations_active ?? '—'} />
          <Kpi label="Trials" value={summary?.organizations_trialing ?? '—'} />
          <Kpi label="Past due" value={summary?.subscriptions_past_due ?? '—'} />
        </section>

        <section className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-bold">Organizaciones recientes</h2>
              <Link href="/admin/organizations/new" className="text-sm font-semibold text-[#c9a040]">Nueva</Link>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-[#a79f91]"><tr><th className="py-2">Cliente</th><th>Plan</th><th>Tier</th><th>Admin cliente</th></tr></thead>
                <tbody>
                  {organizations.map((org) => (
                    <tr key={org.id} className="border-t border-white/10">
                      <td className="py-3"><div className="font-semibold">{org.name}</div><div className="text-xs text-[#a79f91]">{org.slug}</div></td>
                      <td>{org.plan ?? 'starter'}</td>
                      <td>{org.customer_tier ?? 'standard'}</td>
                      <td><Link className="text-[#c9a040]" href={org.admin_path || `/${org.slug}/admin`}>{org.admin_path || `/${org.slug}/admin`}</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-3xl border border-[#c9a040]/30 bg-[#c9a040]/10 p-5">
            <p className="text-xs uppercase tracking-[0.25em] text-[#f2cb68]">Lead client</p>
            <h2 className="mt-2 text-2xl font-black">{leadClient?.name || 'Kairos'}</h2>
            <p className="mt-2 text-sm text-[#d8cbb8]">Tenant de referencia para validar funcionalidades antes de replicarlas a clientes Polkorp.</p>
            <div className="mt-5 space-y-2 text-sm text-[#d8cbb8]">
              <div><b>Slug:</b> {leadClient?.slug || 'kairos'}</div>
              <div><b>Plan:</b> {leadClient?.plan || 'pro'}</div>
              <div><b>Admin:</b> {leadClient?.admin_path || '/kairos/admin'}</div>
            </div>
            <Link href={leadClient?.admin_path || '/kairos/admin'} className="mt-5 inline-flex rounded-xl bg-[#c9a040] px-4 py-3 font-bold text-black">Abrir Kairos</Link>
          </div>
        </section>
      </div>
    </main>
  )
}

function Kpi({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
      <p className="text-sm text-[#a79f91]">{label}</p>
      <div className="mt-2 text-3xl font-black">{value}</div>
    </div>
  )
}

'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import { createPlatformOrganization } from '@/lib/platformApi'

const initialForm = {
  name: '',
  slug: '',
  plan_id: 'starter',
  owner_email: '',
  owner_name: '',
  status: 'trialing',
  customer_tier: 'standard',
  logo_url: '',
  primary_domain: '',
  subdomain: '',
  admin_path: '',
  brand_primary_color: '#C9A040',
  brand_secondary_color: '#2C1F16',
  brand_accent_color: '#FAF7F2',
  public_catalog_enabled: true,
  internal_notes: '',
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/-{2,}/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
}

export default function NewOrganizationPage() {
  const [form, setForm] = useState(initialForm)
  const [slugTouched, setSlugTouched] = useState(false)
  const [saving, setSaving] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')

  const preview = useMemo(() => {
    const slug = form.slug || slugify(form.name) || 'cliente'
    const subdomain = form.subdomain || slug
    return {
      slug,
      primary_domain: form.primary_domain || `${subdomain}.polkorp.com`,
      admin_path: form.admin_path || `/${slug}/admin`,
    }
  }, [form])

  const set = (key: string, value: any) => setForm((prev) => ({ ...prev, [key]: value }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    setResult(null)
    try {
      const payload = {
        ...form,
        slug: preview.slug,
        primary_domain: preview.primary_domain,
        admin_path: preview.admin_path,
        subdomain: form.subdomain || preview.slug,
        feature_flags: {
          public_catalog: form.public_catalog_enabled,
          ai_scoring: form.plan_id === 'pro' || form.plan_id === 'enterprise',
          white_label: form.plan_id === 'pro' || form.plan_id === 'enterprise',
        },
        brand_settings: {
          logo_url: form.logo_url,
          primary_domain: preview.primary_domain,
          admin_path: preview.admin_path,
        },
      }
      const data = await createPlatformOrganization(payload)
      setResult(data)
    } catch (err: any) {
      setError(err.message || 'No se pudo crear la organización')
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="min-h-screen bg-[#07080b] text-[#f7f2e8]">
      <div className="mx-auto max-w-5xl px-6 py-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <Link href="/admin" className="text-sm text-[#c9a040]">← Volver al Admin</Link>
            <h1 className="mt-3 text-4xl font-black">Crear nueva organización</h1>
            <p className="mt-2 text-[#a79f91]">Alta completa de cliente SaaS: workspace, branding, dominio, owner y plan.</p>
          </div>
        </div>

        {error && <div className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">{error}</div>}
        {result && (
          <div className="mb-5 rounded-xl border border-green-500/30 bg-green-500/10 p-4 text-green-200">
            Organización creada. Admin cliente: <Link href={result.urls?.client_admin_url || preview.admin_path} className="underline">{result.urls?.client_admin_url || preview.admin_path}</Link>
          </div>
        )}

        <form onSubmit={submit} className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="space-y-5 rounded-3xl border border-white/10 bg-white/[0.04] p-6">
            <Field label="Nombre empresa">
              <input
                value={form.name}
                onChange={(e) => {
                  set('name', e.target.value)
                  if (!slugTouched) set('slug', slugify(e.target.value))
                }}
                className="input"
                required
              />
            </Field>
            <Field label="Slug">
              <input
                value={form.slug}
                onChange={(e) => {
                  setSlugTouched(true)
                  set('slug', slugify(e.target.value))
                }}
                className="input"
                required
              />
            </Field>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Plan"><select value={form.plan_id} onChange={(e) => set('plan_id', e.target.value)} className="input"><option value="starter">Starter</option><option value="growth">Growth</option><option value="pro">Pro</option><option value="enterprise">Enterprise</option></select></Field>
              <Field label="Estado"><select value={form.status} onChange={(e) => set('status', e.target.value)} className="input"><option value="trialing">Trial</option><option value="active">Activo</option><option value="paused">Pausado</option></select></Field>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Owner email"><input value={form.owner_email} onChange={(e) => set('owner_email', e.target.value)} className="input" type="email" /></Field>
              <Field label="Owner nombre"><input value={form.owner_name} onChange={(e) => set('owner_name', e.target.value)} className="input" /></Field>
            </div>
            <Field label="Notas internas"><textarea value={form.internal_notes} onChange={(e) => set('internal_notes', e.target.value)} className="input min-h-24" /></Field>
          </section>

          <section className="space-y-5 rounded-3xl border border-white/10 bg-white/[0.04] p-6">
            <Field label="Logo URL"><input value={form.logo_url} onChange={(e) => set('logo_url', e.target.value)} className="input" placeholder="https://..." /></Field>
            <div className="grid gap-4 md:grid-cols-3">
              <Field label="Primary"><input value={form.brand_primary_color} onChange={(e) => set('brand_primary_color', e.target.value)} className="input" /></Field>
              <Field label="Secondary"><input value={form.brand_secondary_color} onChange={(e) => set('brand_secondary_color', e.target.value)} className="input" /></Field>
              <Field label="Accent"><input value={form.brand_accent_color} onChange={(e) => set('brand_accent_color', e.target.value)} className="input" /></Field>
            </div>
            <Field label="Subdominio"><input value={form.subdomain} onChange={(e) => set('subdomain', slugify(e.target.value))} className="input" placeholder={preview.slug} /></Field>
            <Field label="Dominio principal"><input value={form.primary_domain} onChange={(e) => set('primary_domain', e.target.value)} className="input" placeholder={preview.primary_domain} /></Field>
            <Field label="Client admin path"><input value={form.admin_path} onChange={(e) => set('admin_path', e.target.value)} className="input" placeholder={preview.admin_path} /></Field>
            <label className="flex items-center gap-3 text-sm text-[#d8cbb8]"><input type="checkbox" checked={form.public_catalog_enabled} onChange={(e) => set('public_catalog_enabled', e.target.checked)} /> Public catalog enabled</label>
            <div className="rounded-2xl border border-[#c9a040]/25 bg-[#c9a040]/10 p-4 text-sm text-[#eadfca]">
              <div><b>Dominio:</b> {preview.primary_domain}</div>
              <div><b>Admin cliente:</b> {preview.admin_path}</div>
              <div><b>Platform:</b> /admin</div>
            </div>
            <button disabled={saving} className="w-full rounded-xl bg-[#c9a040] px-4 py-3 font-black text-black disabled:opacity-50">{saving ? 'Creando...' : 'Crear organización'}</button>
          </section>
        </form>
      </div>
      <style jsx>{`.input{width:100%;border-radius:14px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);padding:12px 14px;color:#f7f2e8;outline:none}.input::placeholder{color:#7b746b} option{color:#111}`}</style>
    </main>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block"><span className="mb-1.5 block text-sm text-[#a79f91]">{label}</span>{children}</label>
}

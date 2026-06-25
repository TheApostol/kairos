'use client'

import Link from 'next/link'
import { useState } from 'react'
import { checkProductOnline } from '@/lib/productIntelligenceApi'

export default function ProductCheckPage() {
  const [form, setForm] = useState({ sku: '', name: '', brand: '', current_image_url: '' })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')

  const set = (key: string, value: string) => setForm((prev) => ({ ...prev, [key]: value }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    try {
      setResult(await checkProductOnline(form))
    } catch (err: any) {
      setError(err.message || 'No se pudo verificar el producto')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-[#07080b] text-[#f7f2e8]">
      <div className="mx-auto max-w-5xl px-6 py-8">
        <Link href="/admin" className="text-sm text-[#c9a040]">← Volver al Admin</Link>
        <h1 className="mt-3 text-4xl font-black">SKU / Product Image Checker</h1>
        <p className="mt-2 text-[#a79f91]">Chequea SKU, nombre y marca online; sugiere fuentes para imágenes faltantes.</p>

        <form onSubmit={submit} className="mt-8 grid gap-5 rounded-3xl border border-white/10 bg-white/[0.04] p-6 md:grid-cols-2">
          <Field label="SKU"><input value={form.sku} onChange={(e) => set('sku', e.target.value)} className="input" placeholder="SKU o código" /></Field>
          <Field label="Marca"><input value={form.brand} onChange={(e) => set('brand', e.target.value)} className="input" placeholder="Marca" /></Field>
          <Field label="Nombre producto"><input value={form.name} onChange={(e) => set('name', e.target.value)} className="input" placeholder="Nombre completo" /></Field>
          <Field label="Imagen actual URL"><input value={form.current_image_url} onChange={(e) => set('current_image_url', e.target.value)} className="input" placeholder="https://..." /></Field>
          <button disabled={loading} className="rounded-xl bg-[#c9a040] px-4 py-3 font-black text-black disabled:opacity-50 md:col-span-2">{loading ? 'Chequeando...' : 'Check online'}</button>
        </form>

        {error && <div className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">{error}</div>}

        {result && (
          <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_1fr]">
            <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-6">
              <h2 className="text-2xl font-bold">Resultado</h2>
              <div className="mt-4 space-y-2 text-sm text-[#d8cbb8]">
                <div><b>Query:</b> {result.query}</div>
                <div><b>Confianza:</b> {result.confidence}</div>
                <div><b>SKU encontrado:</b> {result.sku_match_found ? 'Sí' : 'No'}</div>
                <div><b>Nombre encontrado:</b> {result.name_match_found ? 'Sí' : 'No'}</div>
                <div><b>Imagen actual:</b> {result.has_current_image ? 'Sí' : 'No'}</div>
                <div><b>Recomendación:</b> {result.recommendation}</div>
              </div>
            </div>

            <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-6">
              <h2 className="text-2xl font-bold">Buscar imágenes</h2>
              <div className="mt-4 space-y-3">
                {(result.image_candidates ?? []).map((item: any) => (
                  <a key={item.provider} href={item.url} target="_blank" className="block rounded-xl border border-white/10 p-3 text-[#c9a040] hover:bg-white/5">{item.provider}</a>
                ))}
              </div>
            </div>

            <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-6 lg:col-span-2">
              <h2 className="text-2xl font-bold">Resultados web</h2>
              <div className="mt-4 space-y-3">
                {(result.web_results ?? []).map((item: any, i: number) => (
                  <a key={`${item.url}-${i}`} href={item.url} target="_blank" className="block rounded-xl border border-white/10 p-3 hover:bg-white/5">
                    <div className="font-semibold text-[#f7f2e8]">{item.title}</div>
                    <div className="mt-1 text-xs text-[#a79f91]">{item.url}</div>
                  </a>
                ))}
              </div>
            </div>
          </section>
        )}
      </div>
      <style jsx>{`.input{width:100%;border-radius:14px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);padding:12px 14px;color:#f7f2e8;outline:none}.input::placeholder{color:#7b746b}`}</style>
    </main>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block"><span className="mb-1.5 block text-sm text-[#a79f91]">{label}</span>{children}</label>
}

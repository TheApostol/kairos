'use client'

import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'

export default function TenantAdminLoginPage() {
  const params = useParams<{ tenant: string }>()
  const tenant = params?.tenant || 'client'
  const router = useRouter()
  const { signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    const { error } = await signIn(email, password)
    setLoading(false)
    if (error) {
      setError(error)
      return
    }
    router.replace(`/${tenant}/admin`)
  }

  return (
    <main className="flex min-h-screen bg-[#07080b] text-[#f7f2e8]">
      <section className="hidden flex-1 items-center justify-center bg-gradient-to-br from-[#2C1F16] to-[#07080b] p-10 lg:flex">
        <div className="max-w-md">
          <p className="text-sm uppercase tracking-[0.35em] text-[#c9a040]">Polkorp Client Portal</p>
          <h1 className="mt-4 text-5xl font-black capitalize">{tenant}</h1>
          <p className="mt-4 text-[#c9b8a8]">Acceso privado al panel operativo de tu empresa: CRM, productos, pedidos, campañas y catálogo.</p>
        </div>
      </section>
      <section className="flex flex-1 items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm rounded-3xl border border-white/10 bg-white/[0.04] p-6 shadow-2xl">
          <p className="text-sm uppercase tracking-[0.25em] text-[#c9a040]">{tenant}</p>
          <h2 className="mt-2 text-3xl font-black">Client Login</h2>
          <p className="mt-2 text-sm text-[#a79f91]">Ingresá al workspace de tu organización.</p>
          <div className="mt-6 space-y-4">
            <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required placeholder="email" className="input" />
            <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required placeholder="password" className="input" />
          </div>
          {error && <p className="mt-4 text-sm text-red-300">{error}</p>}
          <button disabled={loading} className="mt-6 w-full rounded-xl bg-[#c9a040] px-4 py-3 font-black text-black disabled:opacity-50">{loading ? 'Ingresando...' : 'Ingresar'}</button>
        </form>
      </section>
      <style jsx>{`.input{width:100%;border-radius:14px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);padding:12px 14px;color:#f7f2e8;outline:none}.input::placeholder{color:#7b746b}`}</style>
    </main>
  )
}

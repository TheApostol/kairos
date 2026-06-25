'use client'

import { Suspense, useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Loader2, Mail, Lock, Eye, EyeOff } from 'lucide-react'

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  )
}

function LoginForm() {
  const { signIn } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    const { error } = await signIn(email, password)
    setLoading(false)
    if (error) {
      setError(error)
      return
    }
    router.replace(searchParams.get('next') || '/')
  }

  return (
    <div className="flex min-h-screen" style={{ backgroundColor: '#FAF7F2' }}>
      <div
        className="hidden lg:flex lg:w-1/2 flex-col items-center justify-center relative overflow-hidden px-12"
        style={{ background: 'linear-gradient(135deg, #2C1F16 0%, #3D2B1F 100%)' }}
      >
        <div className="absolute -top-24 -right-24 w-72 h-72 rounded-full opacity-10" style={{ backgroundColor: '#C9A040' }} />
        <div className="absolute bottom-0 -left-16 w-64 h-64 rounded-full opacity-10" style={{ backgroundColor: '#C9A040' }} />
        <div className="relative z-10 text-center max-w-md">
          <Image src="/dashboard/logo.svg" alt="Kairos Distribuidora" width={260} height={90} priority className="h-20 w-auto mx-auto mb-8" />
          <h2 className="text-2xl font-bold mb-3" style={{ color: '#FAF7F2' }}>Gestioná tu negocio mayorista</h2>
          <p className="text-sm" style={{ color: '#C9B8A8' }}>
            Leads, pedidos, catálogo y equipo, todo en un solo lugar.
          </p>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm">
          <div className="flex justify-center mb-6 lg:hidden">
            <Image src="/dashboard/logo.svg" alt="Kairos Distribuidora" width={220} height={80} priority className="h-16 w-auto" />
          </div>
          <div className="rounded-xl shadow-sm p-6 sm:p-8" style={{ backgroundColor: '#fff', border: '1px solid #E8DDD5' }}>
            <h1 className="text-2xl font-bold mb-1" style={{ color: '#2C1F16' }}>Iniciar sesión</h1>
            <p className="text-sm mb-6" style={{ color: '#6B4F3A' }}>Accedé a tu panel de Kairos CRM</p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: '#B8A595' }} />
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="tu@email.com"
                    className="pl-9"
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Contraseña</Label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: '#B8A595' }} />
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="pl-9 pr-9"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2"
                    style={{ color: '#B8A595' }}
                    tabIndex={-1}
                    aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {error && (
                <p className="text-sm text-red-600">{error}</p>
              )}

              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                Ingresar
              </Button>
            </form>

            <p className="text-sm mt-4 text-center" style={{ color: '#6B4F3A' }}>
              ¿No tenés cuenta?{' '}
              <Link href="/signup" className="font-semibold" style={{ color: '#C9A040' }}>
                Crear cuenta
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

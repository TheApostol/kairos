'use client'

import { Suspense, useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Loader2 } from 'lucide-react'

export default function SignupPage() {
  return (
    <Suspense fallback={null}>
      <SignupForm />
    </Suspense>
  )
}

function SignupForm() {
  const { signUp } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfo(null)

    if (password !== confirmPassword) {
      setError('Las contraseñas no coinciden')
      return
    }
    if (password.length < 6) {
      setError('La contraseña debe tener al menos 6 caracteres')
      return
    }

    setLoading(true)
    const { error } = await signUp(email, password)
    setLoading(false)
    if (error) {
      setError(error)
      return
    }

    setInfo('Cuenta creada. Si tu organización requiere verificación de email, revisá tu casilla. Luego podés iniciar sesión.')
    const next = searchParams.get('next')
    setTimeout(() => router.replace(next ? `/login?next=${encodeURIComponent(next)}` : '/login'), 2500)
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4" style={{ backgroundColor: '#FAF7F2' }}>
      <div className="w-full max-w-sm">
        <div className="flex justify-center mb-6">
          <Image src="/logo.svg" alt="Kairos Distribuidora" width={220} height={80} priority className="h-16 w-auto" />
        </div>
        <div className="rounded-xl shadow-sm p-6" style={{ backgroundColor: '#fff', border: '1px solid #E8DDD5' }}>
          <h1 className="text-xl font-bold mb-1" style={{ color: '#2C1F16' }}>Crear cuenta</h1>
          <p className="text-sm mb-6" style={{ color: '#6B4F3A' }}>Registrate para acceder a Kairos CRM</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="tu@email.com"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Contraseña</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirmPassword">Confirmar contraseña</Label>
              <Input
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>

            {error && (
              <p className="text-sm text-red-600">{error}</p>
            )}
            {info && (
              <p className="text-sm" style={{ color: '#15803d' }}>{info}</p>
            )}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              Crear cuenta
            </Button>
          </form>

          <p className="text-sm mt-4 text-center" style={{ color: '#6B4F3A' }}>
            ¿Ya tenés cuenta?{' '}
            <Link href="/login" className="font-semibold" style={{ color: '#C9A040' }}>
              Iniciar sesión
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

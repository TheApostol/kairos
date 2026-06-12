'use client'

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { useAuth } from '@/contexts/AuthContext'
import { acceptInvitation } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Loader2, CheckCircle2, XCircle } from 'lucide-react'

export default function AcceptInvitePage() {
  return (
    <Suspense fallback={null}>
      <AcceptInviteContent />
    </Suspense>
  )
}

function AcceptInviteContent() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get('token') || ''

  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (authLoading) return
    if (!user) return
    if (!token) {
      setStatus('error')
      setError('Falta el token de invitación.')
      return
    }

    setStatus('loading')
    acceptInvitation(token)
      .then(() => {
        setStatus('success')
        setTimeout(() => router.replace('/'), 2000)
      })
      .catch((err) => {
        setStatus('error')
        setError(err instanceof Error ? err.message : 'No se pudo aceptar la invitación.')
      })
  }, [authLoading, user, token, router])

  return (
    <div className="flex min-h-screen items-center justify-center px-4" style={{ backgroundColor: '#FAF7F2' }}>
      <div className="w-full max-w-sm">
        <div className="flex justify-center mb-6">
          <Image src="/logo.svg" alt="Kairos Distribuidora" width={220} height={80} priority className="h-16 w-auto" />
        </div>
        <div className="rounded-xl shadow-sm p-6 text-center" style={{ backgroundColor: '#fff', border: '1px solid #E8DDD5' }}>
          {authLoading || status === 'loading' ? (
            <>
              <Loader2 className="w-8 h-8 mx-auto mb-3 animate-spin" style={{ color: '#C9A040' }} />
              <p className="text-sm" style={{ color: '#6B4F3A' }}>Procesando invitación...</p>
            </>
          ) : !user ? (
            <>
              <h1 className="text-xl font-bold mb-2" style={{ color: '#2C1F16' }}>Invitación a Kairos CRM</h1>
              <p className="text-sm mb-4" style={{ color: '#6B4F3A' }}>
                Iniciá sesión o creá una cuenta para aceptar la invitación.
              </p>
              <div className="flex flex-col gap-2">
                <Button asChild className="w-full">
                  <Link href={`/login?next=/accept-invite?token=${encodeURIComponent(token)}`}>Iniciar sesión</Link>
                </Button>
                <Button asChild variant="outline" className="w-full">
                  <Link href={`/signup?next=/accept-invite?token=${encodeURIComponent(token)}`}>Crear cuenta</Link>
                </Button>
              </div>
            </>
          ) : status === 'success' ? (
            <>
              <CheckCircle2 className="w-8 h-8 mx-auto mb-3" style={{ color: '#15803d' }} />
              <p className="text-sm font-medium" style={{ color: '#2C1F16' }}>¡Invitación aceptada!</p>
              <p className="text-sm mt-1" style={{ color: '#6B4F3A' }}>Redirigiendo al panel...</p>
            </>
          ) : status === 'error' ? (
            <>
              <XCircle className="w-8 h-8 mx-auto mb-3" style={{ color: '#dc2626' }} />
              <p className="text-sm font-medium" style={{ color: '#2C1F16' }}>No se pudo aceptar la invitación</p>
              {error && <p className="text-sm mt-1" style={{ color: '#6B4F3A' }}>{error}</p>}
              <Button asChild className="w-full mt-4">
                <Link href="/">Ir al panel</Link>
              </Button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}

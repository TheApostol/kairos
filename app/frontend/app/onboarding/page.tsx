'use client'

import { useEffect, useState } from 'react'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { getMyOrganization, createOrganization } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Loader2 } from 'lucide-react'

function slugify(value: string) {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export default function OnboardingPage() {
  const { signOut } = useAuth()
  const router = useRouter()
  const [checking, setChecking] = useState(true)
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [slugEdited, setSlugEdited] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getMyOrganization()
      .then(() => router.replace('/'))
      .catch(() => setChecking(false))
  }, [router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!name.trim() || !slug.trim()) return
    setCreating(true)
    try {
      await createOrganization({ name: name.trim(), slug: slug.trim() })
      router.replace('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo crear la organización')
    } finally {
      setCreating(false)
    }
  }

  if (checking) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ backgroundColor: '#FAF7F2' }}>
        <Loader2 className="w-6 h-6 animate-spin" style={{ color: '#C9A040' }} />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4" style={{ backgroundColor: '#FAF7F2' }}>
      <div className="w-full max-w-sm">
        <div className="flex justify-center mb-6">
          <Image src="/logo.svg" alt="Kairos Distribuidora" width={220} height={80} priority className="h-16 w-auto" />
        </div>
        <div className="rounded-xl shadow-sm p-6" style={{ backgroundColor: '#fff', border: '1px solid #E8DDD5' }}>
          <h1 className="text-xl font-bold mb-1" style={{ color: '#2C1F16' }}>Creá tu organización</h1>
          <p className="text-sm mb-6" style={{ color: '#6B4F3A' }}>
            Tu cuenta todavía no pertenece a ninguna organización. Si te invitaron, pedile a quien te invitó
            que te reenvíe el link de invitación. Si no, podés crear una organización nueva.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="orgName">Nombre de la organización</Label>
              <Input
                id="orgName"
                required
                value={name}
                onChange={(e) => {
                  const value = e.target.value
                  setName(value)
                  if (!slugEdited) setSlug(slugify(value))
                }}
                placeholder="Mi Empresa"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="orgSlug">Identificador (slug)</Label>
              <Input
                id="orgSlug"
                required
                value={slug}
                onChange={(e) => {
                  setSlugEdited(true)
                  setSlug(slugify(e.target.value))
                }}
                placeholder="mi-empresa"
              />
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <Button type="submit" className="w-full" disabled={creating}>
              {creating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              Crear organización
            </Button>
          </form>

          <button
            onClick={() => signOut()}
            className="text-sm mt-4 w-full text-center"
            style={{ color: '#6B4F3A' }}
          >
            Cerrar sesión
          </button>
        </div>
      </div>
    </div>
  )
}

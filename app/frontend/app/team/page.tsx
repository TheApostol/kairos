'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  getMyOrganization,
  getInvitations,
  createInvitation,
  revokeInvitation,
  updateMember,
  removeMember,
} from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import { Loader2, UserPlus, Trash2, Building2, LogOut, Copy, Check } from 'lucide-react'

interface Member {
  user_id: string
  email: string
  role: string
  status: string
  created_at?: string
}

interface Invitation {
  id: string
  email: string
  role: string
  token?: string
  created_at?: string
}

interface OrgMeResponse {
  organization: { id: string; name: string; slug: string }
  role: string
  user_id: string
  email: string
  members: Member[]
}

const ROLE_LABELS: Record<string, string> = {
  owner: 'Propietario',
  admin: 'Administrador',
  sales: 'Ventas',
  viewer: 'Solo lectura',
}

export default function TeamPage() {
  const { user, signOut } = useAuth()
  const [data, setData] = useState<OrgMeResponse | null>(null)
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('sales')
  const [inviting, setInviting] = useState(false)
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const canManage = data?.role === 'owner' || data?.role === 'admin'

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const org = await getMyOrganization()
      setData(org)
      if (org.role === 'owner' || org.role === 'admin') {
        const inv = await getInvitations()
        setInvitations(inv.items ?? [])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar la organización')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    setInviteError(null)
    if (!inviteEmail.trim()) return
    setInviting(true)
    try {
      await createInvitation({ email: inviteEmail.trim(), role: inviteRole })
      setInviteEmail('')
      await load()
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : 'No se pudo enviar la invitación')
    } finally {
      setInviting(false)
    }
  }

  const handleCopyInviteLink = async (inv: Invitation) => {
    if (!inv.token) return
    const url = `${window.location.origin}/accept-invite?token=${inv.token}`
    await navigator.clipboard.writeText(url)
    setCopiedId(inv.id)
    setTimeout(() => setCopiedId((current) => (current === inv.id ? null : current)), 2000)
  }

  const handleRevoke = async (invitationId: string) => {
    await revokeInvitation(invitationId)
    await load()
  }

  const handleRoleChange = async (userId: string, role: string) => {
    await updateMember(userId, { role })
    await load()
  }

  const handleStatusToggle = async (member: Member) => {
    const newStatus = member.status === 'active' ? 'disabled' : 'active'
    await updateMember(member.user_id, { status: newStatus })
    await load()
  }

  const handleRemove = async (userId: string) => {
    await removeMember(userId)
    await load()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="w-6 h-6 animate-spin" style={{ color: '#C9A040' }} />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-2xl mx-auto py-12 text-center">
        <p className="text-sm text-red-600">{error ?? 'No se pudo cargar la organización'}</p>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: '#2C1F16' }}
          >
            <Building2 className="w-5 h-5" style={{ color: '#C9A040' }} />
          </div>
          <div>
            <h1 className="text-xl font-bold" style={{ color: '#2C1F16' }}>{data.organization.name}</h1>
            <p className="text-sm" style={{ color: '#6B4F3A' }}>
              {user?.email} · {ROLE_LABELS[data.role] ?? data.role}
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => signOut()}>
          <LogOut className="w-4 h-4 mr-2" />
          Cerrar sesión
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Miembros</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {data.members.map((member) => (
              <div
                key={member.user_id}
                className="flex flex-wrap items-center justify-between gap-2 py-2 border-b last:border-0"
                style={{ borderColor: '#E8DDD5' }}
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate" style={{ color: '#2D1F17' }}>
                    {member.email || member.user_id}
                  </p>
                  <p className="text-xs" style={{ color: '#94A3B8' }}>
                    {member.status === 'active' ? 'Activo' : 'Deshabilitado'}
                  </p>
                </div>
                {canManage ? (
                  <div className="flex items-center gap-2">
                    <Select value={member.role} onValueChange={(v) => handleRoleChange(member.user_id, v)}>
                      <SelectTrigger className="w-36 h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="owner">Propietario</SelectItem>
                        <SelectItem value="admin">Administrador</SelectItem>
                        <SelectItem value="sales">Ventas</SelectItem>
                        <SelectItem value="viewer">Solo lectura</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button variant="outline" size="sm" onClick={() => handleStatusToggle(member)}>
                      {member.status === 'active' ? 'Deshabilitar' : 'Habilitar'}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleRemove(member.user_id)}
                      title="Quitar de la organización"
                    >
                      <Trash2 className="w-4 h-4" style={{ color: '#dc2626' }} />
                    </Button>
                  </div>
                ) : (
                  <span
                    className="text-xs font-semibold px-2 py-1 rounded-full"
                    style={{ backgroundColor: '#F1E9DF', color: '#6B4F3A' }}
                  >
                    {ROLE_LABELS[member.role] ?? member.role}
                  </span>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {canManage && (
        <Card>
          <CardHeader>
            <CardTitle>Invitar miembro</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={handleInvite} className="flex flex-wrap items-end gap-3">
              <div className="space-y-1.5 flex-1 min-w-[200px]">
                <Label htmlFor="inviteEmail">Email</Label>
                <Input
                  id="inviteEmail"
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="persona@empresa.com"
                />
              </div>
              <div className="space-y-1.5 w-40">
                <Label>Rol</Label>
                <Select value={inviteRole} onValueChange={setInviteRole}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">Administrador</SelectItem>
                    <SelectItem value="sales">Ventas</SelectItem>
                    <SelectItem value="viewer">Solo lectura</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button type="submit" disabled={inviting}>
                {inviting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <UserPlus className="w-4 h-4 mr-2" />}
                Invitar
              </Button>
            </form>
            {inviteError && <p className="text-sm text-red-600">{inviteError}</p>}

            {invitations.length > 0 && (
              <div className="space-y-2 pt-2">
                <p className="text-xs font-semibold uppercase" style={{ color: '#94A3B8' }}>Invitaciones pendientes</p>
                <p className="text-xs" style={{ color: '#94A3B8' }}>
                  Si la persona invitada no recibe el email, copiá el enlace y enviáselo manualmente.
                </p>
                {invitations.map((inv) => (
                  <div
                    key={inv.id}
                    className="flex items-center justify-between gap-2 py-2 border-b last:border-0"
                    style={{ borderColor: '#E8DDD5' }}
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate" style={{ color: '#2D1F17' }}>{inv.email}</p>
                      <p className="text-xs" style={{ color: '#94A3B8' }}>{ROLE_LABELS[inv.role] ?? inv.role}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {inv.token && (
                        <Button variant="outline" size="sm" onClick={() => handleCopyInviteLink(inv)} title="Copiar enlace de invitación">
                          {copiedId === inv.id ? (
                            <Check className="w-4 h-4 text-green-600" />
                          ) : (
                            <Copy className="w-4 h-4" />
                          )}
                        </Button>
                      )}
                      <Button variant="outline" size="sm" onClick={() => handleRevoke(inv.id)}>
                        <Trash2 className="w-4 h-4" style={{ color: '#dc2626' }} />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

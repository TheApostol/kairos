'use client'

import { useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import MobileLayout from './MobileLayout'

const PUBLIC_PREFIXES = ['/login', '/signup', '/accept-invite', '/public']
const NO_LAYOUT_PREFIXES = ['/onboarding', '/platform', '/admin']

function isTenantAdminLogin(pathname: string) {
  return /^\/[^/]+\/admin\/login$/.test(pathname)
}

function isTenantAdminPath(pathname: string) {
  return /^\/[^/]+\/admin(\/.*)?$/.test(pathname)
}

function isPublicPath(pathname: string) {
  return PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`)) || isTenantAdminLogin(pathname)
}

function isNoLayoutPath(pathname: string) {
  return NO_LAYOUT_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`)) || isTenantAdminPath(pathname)
}

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const pathname = usePathname()
  const router = useRouter()
  const isPublic = isPublicPath(pathname)
  const isNoLayout = isNoLayoutPath(pathname)

  useEffect(() => {
    if (loading) return
    if (!user && !isPublic) {
      const next = pathname.startsWith('/admin') || pathname.startsWith('/platform') ? '/admin' : pathname
      router.replace(`/login?next=${encodeURIComponent(next)}`)
    } else if (user && (pathname === '/login' || pathname === '/signup')) {
      router.replace('/')
    }
  }, [loading, user, isPublic, pathname, router])

  if (isPublic) {
    return <>{children}</>
  }

  if (loading || !user) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ backgroundColor: '#FAF7F2' }}>
        <div
          className="w-8 h-8 rounded-full border-2 border-t-transparent animate-spin"
          style={{ borderColor: '#C9A040', borderTopColor: 'transparent' }}
        />
      </div>
    )
  }

  if (isNoLayout) {
    return <>{children}</>
  }

  return <MobileLayout>{children}</MobileLayout>
}

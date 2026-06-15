'use client'

import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  Users,
  KanbanSquare,
  Megaphone,
  ShoppingCart,
  BookOpen,
  Search,
  Building2,
  UsersRound,
  LogOut,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { getLeads } from '@/lib/api'
import { useScraperStatus } from '@/contexts/ScraperStatusContext'
import { useAuth } from '@/contexts/AuthContext'

const navGroups = [
  {
    label: 'General',
    items: [
      { href: '/', label: 'Dashboard', icon: LayoutDashboard },
      { href: '/leads', label: 'Leads', icon: Users, badge: true },
      { href: '/pipeline', label: 'Pipeline', icon: KanbanSquare },
    ],
  },
  {
    label: 'Ventas',
    items: [
      { href: '/mayoristas', label: 'Mayoristas', icon: Building2 },
      { href: '/campaigns', label: 'Campañas', icon: Megaphone },
      { href: '/orders', label: 'Órdenes', icon: ShoppingCart },
    ],
  },
  {
    label: 'Recursos',
    items: [
      { href: '/catalog', label: 'Catálogo', icon: BookOpen },
      { href: '/scraper', label: 'Scraper', icon: Search },
      { href: '/team', label: 'Equipo', icon: UsersRound },
    ],
  },
]

interface SidebarProps {
  onClose?: () => void
}

export default function Sidebar({ onClose }: SidebarProps) {
  const pathname = usePathname()
  const [leadCount, setLeadCount] = useState<number | null>(null)
  const { isRunning: scraperRunning, progress: scraperProgress } = useScraperStatus()
  const { user, signOut } = useAuth()

  useEffect(() => {
    getLeads({ limit: 1 })
      .then((data) => {
        if (data?.total !== undefined) setLeadCount(data.total)
      })
      .catch(() => {})
  }, [])

  return (
    <aside
      className="w-64 flex-shrink-0 flex flex-col"
      style={{ backgroundColor: '#2C1F16' }}
    >
      {/* Logo */}
      <div
        className="flex items-center justify-between px-4 py-6 border-b"
        style={{ borderColor: '#3D2B1F' }}
      >
        <Image
          src="/logo.svg"
          alt="Kairos Distribuidora"
          width={220}
          height={80}
          priority
          className="h-20 w-auto"
        />
        {onClose && (
          <button
            onClick={onClose}
            className="lg:hidden p-1.5 rounded-md flex-shrink-0"
            style={{ color: '#FAF7F2' }}
            aria-label="Cerrar menú"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-5 overflow-y-auto">
        {navGroups.map((group) => (
          <div key={group.label}>
            <p
              className="px-3 mb-1.5 text-[11px] font-semibold uppercase tracking-wider"
              style={{ color: '#8A6F5C' }}
            >
              {group.label}
            </p>
            <div className="space-y-1">
              {group.items.map(({ href, label, icon: Icon, badge }) => {
                const isActive =
                  href === '/' ? pathname === '/' : pathname.startsWith(href)
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={onClose}
                    className={cn(
                      'flex items-center gap-3 pl-3 pr-3 py-2.5 rounded-lg text-sm font-medium transition-colors group border-l-[3px]'
                    )}
                    style={
                      isActive
                        ? { backgroundColor: 'rgba(201,160,64,0.16)', color: '#F5E6C8', borderLeftColor: '#C9A040' }
                        : { color: '#D9CBBF', borderLeftColor: 'transparent' }
                    }
                    onMouseEnter={(e) => {
                      if (!isActive) {
                        (e.currentTarget as HTMLElement).style.backgroundColor = '#3D2B1F'
                        ;(e.currentTarget as HTMLElement).style.color = '#FAF7F2'
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) {
                        (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'
                        ;(e.currentTarget as HTMLElement).style.color = '#D9CBBF'
                      }
                    }}
                  >
                    <Icon className="w-5 h-5 flex-shrink-0" style={isActive ? { color: '#C9A040' } : undefined} />
                    <span className="flex-1">{label}</span>
                    {badge && leadCount !== null && (
                      <span
                        className="text-xs font-bold px-2 py-0.5 rounded-full"
                        style={
                          isActive
                            ? { backgroundColor: '#2C1F16', color: '#C9A040' }
                            : { backgroundColor: '#C9A040', color: '#2C1F16' }
                        }
                      >
                        {leadCount > 999 ? '999+' : leadCount}
                      </span>
                    )}
                    {href === '/scraper' && scraperRunning && (
                      <span className="flex items-center gap-1">
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                        </span>
                        <span
                          className="text-xs font-semibold"
                          style={{ color: isActive ? '#2C1F16' : '#86efac' }}
                        >
                          {scraperProgress}%
                        </span>
                      </span>
                    )}
                  </Link>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div
        className="px-4 py-4 border-t flex items-center gap-3"
        style={{ borderColor: '#3D2B1F' }}
      >
        <div
          className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold"
          style={{ backgroundColor: '#C9A040', color: '#2C1F16' }}
        >
          {(user?.email?.[0] ?? '?').toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          {user?.email && (
            <p className="text-xs font-medium truncate" style={{ color: '#FAF7F2' }}>
              {user.email}
            </p>
          )}
          <p className="text-xs truncate" style={{ color: '#8A6F5C' }}>
            kairos.polkorp.com
          </p>
        </div>
        <button
          onClick={() => signOut()}
          className="p-1.5 rounded-md flex-shrink-0 transition-colors hover:bg-[#3D2B1F]"
          style={{ color: '#FAF7F2' }}
          aria-label="Cerrar sesión"
          title="Cerrar sesión"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </aside>
  )
}

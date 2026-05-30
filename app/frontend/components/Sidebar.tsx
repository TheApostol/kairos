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
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { getLeads } from '@/lib/api'

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/leads', label: 'Leads', icon: Users, badge: true },
  { href: '/mayoristas', label: 'Mayoristas', icon: Building2 },
  { href: '/pipeline', label: 'Pipeline', icon: KanbanSquare },
  { href: '/campaigns', label: 'Campañas', icon: Megaphone },
  { href: '/orders', label: 'Órdenes', icon: ShoppingCart },
  { href: '/catalog', label: 'Catálogo', icon: BookOpen },
  { href: '/scraper', label: 'Scraper', icon: Search },
]

interface SidebarProps {
  onClose?: () => void
}

export default function Sidebar({ onClose }: SidebarProps) {
  const pathname = usePathname()
  const [leadCount, setLeadCount] = useState<number | null>(null)

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
        className="flex items-center justify-between px-5 py-5 border-b"
        style={{ borderColor: '#3D2B1F' }}
      >
        <Image
          src="/logo.svg"
          alt="Kairos Distribuidora"
          width={200}
          height={64}
          priority
          className="h-14 w-auto"
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
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ href, label, icon: Icon, badge }) => {
          const isActive =
            href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              onClick={onClose}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors group'
              )}
              style={
                isActive
                  ? { backgroundColor: '#C9A040', color: '#2C1F16' }
                  : { color: '#FAF7F2' }
              }
              onMouseEnter={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLElement).style.backgroundColor = '#3D2B1F'
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'
                }
              }}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
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
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div
        className="px-6 py-4 border-t"
        style={{ borderColor: '#3D2B1F' }}
      >
        <p className="text-xs" style={{ color: '#6B4F3A' }}>
          kairos.polkorp.com
        </p>
      </div>
    </aside>
  )
}

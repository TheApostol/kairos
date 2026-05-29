'use client'

import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  Users,
  Megaphone,
  ShoppingCart,
  BookOpen,
  Search,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { getLeads } from '@/lib/api'

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/leads', label: 'Leads', icon: Users, badge: true },
  { href: '/campaigns', label: 'Campañas', icon: Megaphone },
  { href: '/orders', label: 'Órdenes', icon: ShoppingCart },
  { href: '/catalog', label: 'Catálogo', icon: BookOpen },
  { href: '/scraper', label: 'Scraper', icon: Search },
]

export default function Sidebar() {
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
        className="flex items-center px-5 py-4 border-b"
        style={{ borderColor: '#3D2B1F' }}
      >
        <Image
          src="/logo.svg"
          alt="Kairos Distribuidora"
          width={160}
          height={48}
          priority
          className="h-10 w-auto"
        />
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

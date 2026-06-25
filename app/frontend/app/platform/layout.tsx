'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Activity, Building2, ClipboardList, CreditCard, Flag, LayoutDashboard, ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { href: '/admin', label: 'Overview', icon: LayoutDashboard },
  { href: '/admin/organizations', label: 'Organizations', icon: Building2 },
  { href: '/admin/subscriptions', label: 'Subscriptions', icon: CreditCard },
  { href: '/admin/plans', label: 'Plans', icon: ShieldCheck },
  { href: '/admin/usage', label: 'Usage', icon: Activity },
  { href: '/admin/audit-logs', label: 'Audit Logs', icon: ClipboardList },
  { href: '/admin/feature-flags', label: 'Feature Flags', icon: Flag },
]

export default function PlatformLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <aside className="fixed inset-y-0 left-0 hidden w-72 border-r border-slate-800 bg-slate-950 px-4 py-5 lg:block">
        <div className="mb-8 flex items-center gap-3 px-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-amber-400 text-slate-950">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold">Polkorp Admin</p>
            <p className="text-xs text-slate-400">Platform operations</p>
          </div>
        </div>
        <nav className="space-y-1">
          {navItems.map(({ href, label, icon: Icon }) => {
            const active = href === '/admin' ? pathname === href : pathname.startsWith(href)
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                  active ? 'bg-slate-800 text-white' : 'text-slate-400 hover:bg-slate-900 hover:text-white'
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            )
          })}
        </nav>
      </aside>
      <main className="lg:pl-72">
        <div className="mx-auto max-w-7xl px-4 py-5 sm:px-6 lg:px-8">
          <div className="mb-5 flex items-center gap-2 overflow-x-auto border-b border-slate-800 pb-3 lg:hidden">
            {navItems.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  'whitespace-nowrap rounded-md px-3 py-1.5 text-xs',
                  pathname === href ? 'bg-slate-800 text-white' : 'text-slate-400'
                )}
              >
                {label}
              </Link>
            ))}
          </div>
          {children}
        </div>
      </main>
    </div>
  )
}

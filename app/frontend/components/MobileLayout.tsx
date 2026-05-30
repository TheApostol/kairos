'use client'

import { useState } from 'react'
import Image from 'next/image'
import Sidebar from './Sidebar'
import { Menu } from 'lucide-react'

export default function MobileLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden" style={{ backgroundColor: '#FAF7F2' }}>
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 lg:hidden"
          style={{ backgroundColor: 'rgba(0,0,0,0.55)' }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar — fixed overlay on mobile, static on desktop */}
      <div
        className={`
          fixed inset-y-0 left-0 z-50 flex-shrink-0
          transform transition-transform duration-250 ease-in-out
          lg:relative lg:translate-x-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        <Sidebar onClose={() => setSidebarOpen(false)} />
      </div>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile top bar */}
        <header
          className="lg:hidden flex items-center gap-4 px-4 py-4 flex-shrink-0 border-b"
          style={{ backgroundColor: '#2C1F16', borderColor: '#3D2B1F' }}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 rounded-md flex-shrink-0"
            style={{ color: '#FAF7F2' }}
            aria-label="Abrir menú"
          >
            <Menu className="w-6 h-6" />
          </button>
          <Image
            src="/logo.svg"
            alt="Kairos Distribuidora"
            width={180}
            height={56}
            className="h-12 w-auto"
            priority
          />
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <div className="min-h-full p-4 sm:p-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}

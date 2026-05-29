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
          className="lg:hidden flex items-center gap-3 px-4 py-3 flex-shrink-0 border-b"
          style={{ backgroundColor: '#2C1F16', borderColor: '#3D2B1F' }}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 rounded-md flex-shrink-0"
            style={{ color: '#FAF7F2' }}
            aria-label="Abrir menú"
          >
            <Menu className="w-5 h-5" />
          </button>
          <Image
            src="/logo.svg"
            alt="Kairos Distribuidora"
            width={150}
            height={45}
            className="h-8 w-auto"
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

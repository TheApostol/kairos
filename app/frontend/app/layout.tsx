import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import Sidebar from '@/components/Sidebar'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Kairos Distribuidora — CRM',
  description: 'CRM interno para Kairos Distribuidora',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className={inter.className}>
        <div className="flex h-screen overflow-hidden" style={{ backgroundColor: '#FAF7F2' }}>
          <Sidebar />
          <main className="flex-1 overflow-y-auto">
            <div className="min-h-full p-6">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  )
}

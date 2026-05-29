import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import MobileLayout from '@/components/MobileLayout'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Kairos Distribuidora — CRM',
  description: 'CRM interno para Kairos Distribuidora',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className={inter.className}>
        <MobileLayout>
          {children}
        </MobileLayout>
      </body>
    </html>
  )
}

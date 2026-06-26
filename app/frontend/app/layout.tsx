import type { Metadata, Viewport } from 'next'
import './globals.css'
import AuthGate from '@/components/AuthGate'
import { AuthProvider } from '@/contexts/AuthContext'

const basePath = '/dashboard'

export const metadata: Metadata = {
  title: 'Polkorp Suite — Dashboard',
  description: 'Dashboard operativo de Polkorp Suite para administrar clientes, tenants y CRM.',
  manifest: `${basePath}/manifest.json`,
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'Polkorp Suite',
  },
  icons: {
    icon: [
      { url: `${basePath}/polkorp-icon.svg`, type: 'image/svg+xml' },
      { url: `${basePath}/icon-192.png`, sizes: '192x192', type: 'image/png' },
      { url: `${basePath}/icon-512.png`, sizes: '512x512', type: 'image/png' },
    ],
    apple: `${basePath}/polkorp-icon.svg`,
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: '#050914',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <head>
        <link rel="manifest" href={`${basePath}/manifest.json`} />
        <meta name="mobile-web-app-capable" content="yes" />
      </head>
      <body>
        <AuthProvider>
          <AuthGate>
            {children}
          </AuthGate>
        </AuthProvider>
        <script dangerouslySetInnerHTML={{
          __html: `
            if ('serviceWorker' in navigator) {
              window.addEventListener('load', function() {
                navigator.serviceWorker.register('${basePath}/sw.js', { scope: '${basePath}/' });
              });
            }
          `
        }} />
      </body>
    </html>
  )
}

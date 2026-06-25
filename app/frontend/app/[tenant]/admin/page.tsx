'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'

export default function TenantAdminPage() {
  const params = useParams<{ tenant: string }>()
  const tenant = params?.tenant || 'client'

  return (
    <main className="min-h-screen bg-[#FAF7F2] text-[#2C1F16]">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <p className="text-sm uppercase tracking-[0.25em] text-[#C9A040]">Client Workspace</p>
        <h1 className="mt-3 text-4xl font-black capitalize">{tenant} Admin</h1>
        <p className="mt-2 max-w-2xl text-[#6B4F3A]">Panel operativo del cliente. Esta ruta separa el login y experiencia del cliente del panel master de Polkorp.</p>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <Card title="CRM" href="/leads" text="Gestionar leads y pipeline." />
          <Card title="Catálogo" href="/catalog" text="Productos, precios, imágenes y PDF." />
          <Card title="Pedidos" href="/orders" text="Cotizaciones, órdenes y clientes." />
          <Card title="Campañas" href="/campaigns" text="Email, WhatsApp y automatización." />
          <Card title="Scraper" href="/scraper" text="Buscar nuevos leads." />
          <Card title="Equipo" href="/team" text="Usuarios y roles del workspace." />
        </div>
      </div>
    </main>
  )
}

function Card({ title, text, href }: { title: string; text: string; href: string }) {
  return (
    <Link href={href} className="rounded-2xl border border-[#E8DDD5] bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <h2 className="text-xl font-black">{title}</h2>
      <p className="mt-2 text-sm text-[#6B4F3A]">{text}</p>
    </Link>
  )
}

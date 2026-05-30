'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getLeadStats, getOrderStats, getTodayTasks } from '@/lib/api'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
} from 'recharts'
import { Users, Mail, ShoppingBag, TrendingUp, Loader2, AlertCircle, ExternalLink, Building2, Package } from 'lucide-react'
import Link from 'next/link'
import { getLeads, getProducts } from '@/lib/api'

interface RecentLead {
  id: string
  empresa: string
  ciudad?: string
  provincia?: string
  email?: string
  estado: string
  score_ia?: number
  created_at?: string
}

interface CatalogProduct {
  id: number
  nombre: string
  categoria?: string
  precio_minorista?: number
  imagen_url?: string
}

interface LeadStats {
  total: number
  con_email: number
  por_provincia: Array<{ provincia: string; count: number }>
  por_estado: Array<{ estado: string; count: number }>
}

interface OrderStats {
  ordenes_activas: number
  revenue_mes: number
  por_mes: Array<{ mes: string; count: number }>
  revenue_por_mes?: Array<{ mes: string; revenue: number }>
}

const ESTADO_COLORS: Record<string, string> = {
  nuevo: '#C9A040',
  contactado: '#a8832e',
  interesado: '#6B4F3A',
  cliente: '#22c55e',
  descartado: '#9ca3af',
}

const ESTADO_LABELS: Record<string, string> = {
  nuevo: 'Nuevo',
  contactado: 'Contactado',
  interesado: 'Interesado',
  cliente: 'Cliente',
  descartado: 'Descartado',
}

function formatCurrency(n: number) {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n)
}

export default function DashboardPage() {
  const [leadStats, setLeadStats] = useState<LeadStats | null>(null)
  const [orderStats, setOrderStats] = useState<OrderStats | null>(null)
  const [overdueTasksCount, setOverdueTasksCount] = useState<number | null>(null)
  const [recentLeads, setRecentLeads] = useState<RecentLead[]>([])
  const [catalogTotal, setCatalogTotal] = useState<number | null>(null)
  const [catalogPreview, setCatalogPreview] = useState<CatalogProduct[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getLeadStats(), getOrderStats()])
      .then(([ls, os]) => {
        setLeadStats(ls)
        setOrderStats(os)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))

    getTodayTasks()
      .then((res) => setOverdueTasksCount(res?.total ?? 0))
      .catch(() => setOverdueTasksCount(0))

    getLeads({ limit: 8, page: 1 })
      .then((res) => setRecentLeads(res?.items ?? []))
      .catch(() => {})

    getProducts({ page: '1', per_page: '8' })
      .then((res) => {
        setCatalogTotal(res?.total ?? 0)
        setCatalogPreview(res?.items ?? [])
      })
      .catch(() => {})
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin" style={{ color: '#C9A040' }} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        Error al cargar estadísticas: {error}
      </div>
    )
  }

  const totalLeads = leadStats?.total ?? 0
  const clientesCount = (leadStats?.por_estado ?? []).find((e) => e.estado === 'cliente')?.count ?? 0
  const sinEmail = leadStats ? (leadStats.total - leadStats.con_email) : 0
  const conversionRate = totalLeads > 0 ? ((clientesCount / totalLeads) * 100).toFixed(1) : '0'

  const statCards = [
    {
      title: 'Total Leads',
      value: leadStats?.total?.toLocaleString('es-AR') ?? '—',
      icon: Users,
      iconColor: '#C9A040',
      iconBg: 'rgba(201,160,64,0.12)',
      href: '/leads',
    },
    {
      title: 'Con Email',
      value: leadStats?.con_email?.toLocaleString('es-AR') ?? '—',
      icon: Mail,
      iconColor: '#22c55e',
      iconBg: '#f0fdf4',
      href: '/leads',
    },
    {
      title: 'Sin Email',
      value: leadStats ? sinEmail.toLocaleString('es-AR') : '—',
      icon: Mail,
      iconColor: sinEmail > 500 ? '#dc2626' : '#f59e0b',
      iconBg: sinEmail > 500 ? '#fef2f2' : '#fffbeb',
      href: '/scraper',
    },
    {
      title: 'Clientes',
      value: clientesCount.toLocaleString('es-AR'),
      icon: Building2,
      iconColor: '#6B4F3A',
      iconBg: 'rgba(107,79,58,0.1)',
      href: '/leads',
    },
    {
      title: 'Revenue del Mes',
      value: orderStats?.revenue_mes !== undefined ? formatCurrency(orderStats.revenue_mes) : '—',
      icon: TrendingUp,
      iconColor: '#4A3728',
      iconBg: 'rgba(74,55,40,0.1)',
      href: '/orders',
    },
    {
      title: 'Tareas Vencidas',
      value: overdueTasksCount !== null ? overdueTasksCount.toLocaleString('es-AR') : '—',
      icon: AlertCircle,
      iconColor: overdueTasksCount && overdueTasksCount > 0 ? '#dc2626' : '#22c55e',
      iconBg: overdueTasksCount && overdueTasksCount > 0 ? '#fef2f2' : '#f0fdf4',
      urgent: overdueTasksCount !== null && overdueTasksCount > 0,
      href: '/leads',
    },
    {
      title: 'Productos',
      value: catalogTotal !== null ? catalogTotal.toLocaleString('es-AR') : '—',
      icon: Package,
      iconColor: '#C9A040',
      iconBg: 'rgba(201,160,64,0.12)',
      href: '/catalog',
    },
  ]

  const provinciaData = (leadStats?.por_provincia ?? [])
    .slice(0, 8)
    .map((d) => ({ name: d.provincia || 'Sin datos', count: d.count }))

  const estadoData = (leadStats?.por_estado ?? []).map((d) => ({
    name: ESTADO_LABELS[d.estado] ?? d.estado,
    value: d.count,
    estado: d.estado,
  }))

  const mesesData = (orderStats?.por_mes ?? []).map((d) => ({
    name: d.mes,
    ordenes: d.count,
  }))

  const revenueData = (orderStats?.revenue_por_mes ?? []).map((d) => ({
    name: d.mes,
    revenue: d.revenue,
  }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: '#4A3728' }}>Dashboard</h1>
        <p className="mt-1" style={{ color: '#6B4F3A' }}>Resumen general del CRM</p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-4 gap-3">
        {statCards.map(({ title, value, icon: Icon, iconColor, iconBg, href, ...rest }) => {
          const urgent = (rest as { urgent?: boolean }).urgent
          return (
            <Link key={title} href={href ?? '#'}>
              <Card className={`cursor-pointer hover:shadow-md transition-shadow ${urgent ? 'ring-2 ring-red-300' : ''}`}>
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-xs font-medium truncate" style={{ color: '#6B4F3A' }}>{title}</p>
                      <p className={`text-xl font-bold mt-0.5 ${urgent ? 'text-red-600' : ''}`} style={urgent ? undefined : { color: '#4A3728' }}>{value}</p>
                    </div>
                    <div className="p-2 rounded-lg flex-shrink-0" style={{ backgroundColor: iconBg }}>
                      <Icon className="w-4 h-4" style={{ color: iconColor }} />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          )
        })}
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Bar Chart: Leads por Provincia */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold" style={{ color: '#4A3728' }}>Leads por Provincia (top 8)</CardTitle>
          </CardHeader>
          <CardContent>
            {provinciaData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={provinciaData} margin={{ top: 0, right: 16, left: 0, bottom: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0ebe3" />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11, fill: '#6B4F3A' }}
                    angle={-35}
                    textAnchor="end"
                    interval={0}
                  />
                  <YAxis tick={{ fontSize: 11, fill: '#6B4F3A' }} />
                  <Tooltip />
                  <Bar dataKey="count" name="Leads" fill="#C9A040" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-64 flex items-center justify-center" style={{ color: '#6B4F3A' }}>Sin datos</div>
            )}
          </CardContent>
        </Card>

        {/* Pie Chart: Leads por Estado */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold" style={{ color: '#4A3728' }}>Leads por Estado</CardTitle>
          </CardHeader>
          <CardContent>
            {estadoData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={estadoData}
                    cx="50%"
                    cy="45%"
                    outerRadius={90}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {estadoData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={ESTADO_COLORS[entry.estado] ?? '#9ca3af'}
                      />
                    ))}
                  </Pie>
                  <Legend />
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-64 flex items-center justify-center" style={{ color: '#6B4F3A' }}>Sin datos</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Lead Funnel + Recent Leads */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Lead Funnel */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold" style={{ color: '#4A3728' }}>Embudo de Leads</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {estadoData.length > 0 ? estadoData.map((d) => {
              const pct = totalLeads > 0 ? (d.value / totalLeads) * 100 : 0
              return (
                <div key={d.estado} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span style={{ color: '#4A3728' }}>{d.name}</span>
                    <span className="font-semibold" style={{ color: '#4A3728' }}>{d.value.toLocaleString('es-AR')} <span className="text-xs font-normal" style={{ color: '#6B4F3A' }}>({pct.toFixed(1)}%)</span></span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: ESTADO_COLORS[d.estado] ?? '#9ca3af' }} />
                  </div>
                </div>
              )
            }) : <p className="text-slate-400 text-sm">Sin datos</p>}
          </CardContent>
        </Card>

        {/* Recent Leads */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base font-semibold" style={{ color: '#4A3728' }}>Últimos Leads</CardTitle>
              <Link href="/leads" className="text-xs hover:underline" style={{ color: '#C9A040' }}>Ver todos →</Link>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {recentLeads.length === 0 ? (
              <p className="text-sm text-slate-400 px-6 py-4">Sin leads</p>
            ) : (
              <div className="divide-y">
                {recentLeads.map((lead) => (
                  <Link key={lead.id} href={`/leads/${lead.id}`} className="flex items-center justify-between px-6 py-2.5 hover:bg-slate-50 group">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate group-hover:text-amber-700">{lead.empresa}</p>
                      <p className="text-xs text-slate-400">{[lead.ciudad, lead.provincia].filter(Boolean).join(', ') || '—'}</p>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                      {lead.email ? (
                        <span className="w-1.5 h-1.5 rounded-full bg-green-500" title="Tiene email" />
                      ) : (
                        <span className="w-1.5 h-1.5 rounded-full bg-slate-300" title="Sin email" />
                      )}
                      <ExternalLink className="w-3 h-3 text-slate-300" />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2: Activity + Revenue */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold" style={{ color: '#4A3728' }}>Órdenes por Mes</CardTitle>
          </CardHeader>
          <CardContent>
            {mesesData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={mesesData} margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0ebe3" />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#6B4F3A' }} />
                  <YAxis tick={{ fontSize: 12, fill: '#6B4F3A' }} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="ordenes"
                    name="Órdenes"
                    stroke="#C9A040"
                    strokeWidth={2}
                    dot={{ fill: '#C9A040', r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-48 flex items-center justify-center" style={{ color: '#6B4F3A' }}>Sin datos</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold" style={{ color: '#4A3728' }}>Revenue por Mes (ARS)</CardTitle>
          </CardHeader>
          <CardContent>
            {revenueData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={revenueData} margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0ebe3" />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#6B4F3A' }} />
                  <YAxis tick={{ fontSize: 10, fill: '#6B4F3A' }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                  <Tooltip formatter={(value: number) => formatCurrency(value)} />
                  <Bar dataKey="revenue" name="Revenue" fill="#4A3728" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-48 flex items-center justify-center" style={{ color: '#6B4F3A' }}>Sin datos</div>
            )}
          </CardContent>
        </Card>
      </div>
      {/* Catalog Preview */}
      {catalogPreview.length > 0 && (
        <Card>
          <div className="flex items-center justify-between px-6 pt-5 pb-3">
            <div>
              <h2 className="text-base font-semibold" style={{ color: '#4A3728' }}>Catálogo de Productos</h2>
              <p className="text-xs mt-0.5" style={{ color: '#6B4F3A' }}>
                {catalogTotal !== null ? `${catalogTotal.toLocaleString('es-AR')} productos importados` : ''}
              </p>
            </div>
            <Link href="/catalog" className="text-xs hover:underline font-medium" style={{ color: '#C9A040' }}>
              Ver catálogo completo →
            </Link>
          </div>
          <CardContent className="pb-5">
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
              {catalogPreview.map((p) => (
                <Link key={p.id} href="/catalog" className="group text-center">
                  <div className="aspect-square rounded-lg overflow-hidden bg-slate-100 mb-1.5">
                    {p.imagen_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={p.imagen_url}
                        alt={p.nombre}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Package className="w-6 h-6 text-slate-300" />
                      </div>
                    )}
                  </div>
                  <p className="text-xs font-medium text-slate-700 truncate leading-tight">{p.nombre}</p>
                  {p.precio_minorista && (
                    <p className="text-xs mt-0.5" style={{ color: '#C9A040' }}>
                      {new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(p.precio_minorista)}
                    </p>
                  )}
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

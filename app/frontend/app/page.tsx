'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getLeadStats, getOrderStats } from '@/lib/api'
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
import { Users, Mail, ShoppingBag, TrendingUp, Loader2 } from 'lucide-react'

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

  const statCards = [
    {
      title: 'Total Leads',
      value: leadStats?.total?.toLocaleString('es-AR') ?? '—',
      icon: Users,
      iconColor: '#C9A040',
      iconBg: 'rgba(201,160,64,0.12)',
    },
    {
      title: 'Con Email',
      value: leadStats?.con_email?.toLocaleString('es-AR') ?? '—',
      icon: Mail,
      iconColor: '#22c55e',
      iconBg: '#f0fdf4',
    },
    {
      title: 'Órdenes Activas',
      value: orderStats?.ordenes_activas?.toLocaleString('es-AR') ?? '—',
      icon: ShoppingBag,
      iconColor: '#6B4F3A',
      iconBg: 'rgba(107,79,58,0.1)',
    },
    {
      title: 'Revenue del Mes',
      value: orderStats?.revenue_mes !== undefined ? formatCurrency(orderStats.revenue_mes) : '—',
      icon: TrendingUp,
      iconColor: '#4A3728',
      iconBg: 'rgba(74,55,40,0.1)',
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
    campañas: d.count,
  }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: '#4A3728' }}>Dashboard</h1>
        <p className="mt-1" style={{ color: '#6B4F3A' }}>Resumen general del CRM</p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map(({ title, value, icon: Icon, iconColor, iconBg }) => (
          <Card key={title}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium" style={{ color: '#6B4F3A' }}>{title}</p>
                  <p className="text-2xl font-bold mt-1" style={{ color: '#4A3728' }}>{value}</p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: iconBg }}>
                  <Icon className="w-6 h-6" style={{ color: iconColor }} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
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

      {/* Line Chart: Campañas por Mes */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold" style={{ color: '#4A3728' }}>Actividad por Mes</CardTitle>
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
                  dataKey="campañas"
                  stroke="#C9A040"
                  strokeWidth={2}
                  dot={{ fill: '#C9A040', r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-48 flex items-center justify-center" style={{ color: '#6B4F3A' }}>Sin datos de meses</div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

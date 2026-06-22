import { supabase } from './supabaseClient'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://kairos-anuu.onrender.com'

async function getAuthHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const REQUEST_TIMEOUT_MS = 60000

export async function apiFetch(path: string, options?: RequestInit) {
  const authHeader = await getAuthHeader()
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  let res: Response
  try {
    res = await fetch(`${API}${path}`, {
      ...options,
      headers: {
        ...authHeader,
        ...(options?.headers ?? {}),
      },
      signal: controller.signal,
    })
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error('La solicitud tardó demasiado. El servidor puede estar ocupado, intentá de nuevo en un momento.')
    }
    throw err
  } finally {
    clearTimeout(timeout)
  }

  if (!res.ok) {
    const text = await res.text()
    if (
      res.status === 403 &&
      text.includes('not a member of any organization') &&
      typeof window !== 'undefined' &&
      !window.location.pathname.startsWith('/onboarding')
    ) {
      window.location.href = '/onboarding'
    }
    throw new Error(text)
  }
  return res.json()
}

export function getApiUrl(path: string) {
  return `${API}${path}`
}

/**
 * Fetches a file from the API with the auth header attached, then triggers a
 * browser download. Use this instead of `<a href>`/`window.open` for endpoints
 * that require authentication (invoices, exports, price lists, etc).
 */
export async function downloadFile(path: string, filename: string) {
  const authHeader = await getAuthHeader()
  const res = await fetch(`${API}${path}`, { headers: authHeader })
  if (!res.ok) throw new Error(await res.text())
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

/**
 * Builds a URL for an SSE (EventSource) connection, appending the current
 * access token as a query param since EventSource cannot set custom headers.
 */
export async function getEventSourceUrl(path: string) {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  const separator = path.includes('?') ? '&' : '?'
  return `${API}${path}${token ? `${separator}token=${encodeURIComponent(token)}` : ''}`
}

// Leads
export async function getLeads(params?: Record<string, string | number | boolean>) {
  const query = params ? '?' + new URLSearchParams(
    Object.fromEntries(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== '' && v !== null)
        .map(([k, v]) => [k, String(v)])
    )
  ).toString() : ''
  return apiFetch(`/leads${query}`)
}

export async function getLead(id: string | number) {
  return apiFetch(`/leads/${id}`)
}

export async function updateLead(id: string | number, data: Record<string, unknown>) {
  return apiFetch(`/leads/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function createLeadNote(id: string | number, text: string) {
  return apiFetch(`/leads/${id}/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
}

export async function getLeadStats() {
  return apiFetch('/leads/stats')
}

export async function getLeadRubros() {
  return apiFetch('/leads/rubros')
}

// Campaigns
export async function getCampaigns() {
  return apiFetch('/campaigns')
}

export async function getCampaign(id: string | number) {
  return apiFetch(`/campaigns/${id}`)
}

export async function createCampaign(data: Record<string, unknown>) {
  return apiFetch('/campaigns', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function generateCampaignText(data: Record<string, unknown>) {
  return apiFetch('/campaigns/generate-text', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function sendCampaign(id: string | number) {
  return apiFetch(`/campaigns/${id}/send`, {
    method: 'POST',
  })
}

export async function getCampaignStats() {
  return apiFetch('/campaigns/stats')
}

export async function duplicateCampaign(id: string | number) {
  return apiFetch(`/campaigns/${id}/duplicate`, { method: 'POST' })
}

export async function sendCatalogueToClients() {
  return apiFetch('/campaigns/send-catalogue', { method: 'POST' })
}

export async function quickSendLeads(data: {
  lead_ids: number[]
  tipo: 'email' | 'whatsapp'
  asunto?: string
  cuerpo: string
}) {
  return apiFetch('/campaigns/quick-send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function getFollowupWhatsappLinks(diasSinRespuesta: number = 3) {
  return apiFetch(`/campaigns/followup-whatsapp?dias_sin_respuesta=${diasSinRespuesta}`, { method: 'POST' })
}

// Lead Tasks
export async function getLeadTasks(id: string | number) {
  return apiFetch(`/leads/${id}/tasks`)
}

export async function createLeadTask(id: string | number, data: { titulo: string; descripcion?: string; fecha_vencimiento?: string }) {
  return apiFetch(`/leads/${id}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function updateLeadTask(leadId: string | number, taskId: string | number, data: { completado?: boolean; titulo?: string; fecha_vencimiento?: string }) {
  return apiFetch(`/leads/${leadId}/tasks/${taskId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function getTodayTasks() {
  return apiFetch('/leads/tasks/today')
}

// Orders
export async function getOrders(params?: Record<string, string>) {
  const query = params ? '?' + new URLSearchParams(params).toString() : ''
  return apiFetch(`/orders${query}`)
}

export async function getOrder(id: string | number) {
  return apiFetch(`/orders/${id}`)
}

export async function createOrder(data: Record<string, unknown>) {
  return apiFetch('/orders', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function updateOrder(id: string | number, data: Record<string, unknown>) {
  return apiFetch(`/orders/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function getOrderStats() {
  return apiFetch('/orders/stats')
}

// Products / Catalog
export async function getProducts(params?: Record<string, string>) {
  const query = params ? '?' + new URLSearchParams(params).toString() : ''
  return apiFetch(`/products${query}`)
}

export async function getProductCategories() {
  return apiFetch('/products/categories')
}

export async function getProduct(id: string | number) {
  return apiFetch(`/products/${id}`)
}

export async function createProduct(data: Record<string, unknown>) {
  return apiFetch('/products', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function updateProduct(id: string | number, data: Record<string, unknown>) {
  return apiFetch(`/products/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function getProductPriceHistory(id: string | number) {
  return apiFetch(`/products/${id}/price-history`)
}

// Kairosdis Product Scraper
export async function scrapeKairosdis() {
  return apiFetch('/products/scrape-kairosdis', { method: 'POST' })
}

export async function getKairosdisScraperStatus() {
  return apiFetch('/products/scrape-kairosdis/status')
}

// Google Sheets Sync
export async function syncFromGoogleSheet(sheetId: string) {
  return apiFetch('/products/sync-from-sheet', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sheet_id: sheetId }),
  })
}

// Scraper
export const SCRAPER_SOURCES = [
  { id: 'green_life', label: 'Green-Life (Tiendas Naturistas)' },
  { id: 'overpass', label: 'OpenStreetMap (Overpass)' },
  { id: 'datos_gob', label: 'Registro Nacional de Sociedades' },
  { id: 'web_search', label: 'Búsqueda Web (DuckDuckGo)' },
  { id: 'paginas_amarillas', label: 'Páginas Amarillas', experimental: true },
  { id: 'google_places', label: 'Google Places', requiresApiKey: true },
] as const

export const DEFAULT_SCRAPER_SOURCES = ['green_life', 'overpass', 'datos_gob', 'web_search', 'google_places']

export async function getScraperHistory() {
  return apiFetch('/scraper/history')
}

export async function runScraper(
  options: { tipo_cliente?: 'lead' | 'mayorista'; sources?: string[] } | 'lead' | 'mayorista' = 'lead'
) {
  const body =
    typeof options === 'string'
      ? { tipo_cliente: options }
      : { tipo_cliente: options.tipo_cliente ?? 'lead', sources: options.sources }
  return apiFetch('/scraper/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function runEnrichment() {
  return apiFetch('/scraper/enrich', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
}

export async function cancelScraperJob(jobId: string | number) {
  return apiFetch(`/scraper/jobs/${jobId}/cancel`, { method: 'POST' })
}

export async function getDormantClients(dias: number = 30) {
  return apiFetch(`/orders/dormant-clients?dias=${dias}`)
}

export async function getLowStock(threshold: number = 5) {
  return apiFetch(`/products/low-stock?threshold=${threshold}`)
}

// Organizations
export async function getMyOrganization() {
  return apiFetch('/organizations/me')
}

export async function createOrganization(data: { name: string; slug: string }) {
  return apiFetch('/organizations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function acceptInvitation(token: string) {
  return apiFetch('/organizations/accept-invitation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })
}

export async function getInvitations() {
  return apiFetch('/organizations/invitations')
}

export async function createInvitation(data: { email: string; role?: string }) {
  return apiFetch('/organizations/invitations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function revokeInvitation(invitationId: string | number) {
  return apiFetch(`/organizations/invitations/${invitationId}`, { method: 'DELETE' })
}

export async function updateMember(userId: string, data: { role?: string; status?: string }) {
  return apiFetch(`/organizations/members/${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function removeMember(userId: string) {
  return apiFetch(`/organizations/members/${userId}`, { method: 'DELETE' })
}

export const API_BASE = API

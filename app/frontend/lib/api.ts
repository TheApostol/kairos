const API = process.env.NEXT_PUBLIC_API_URL || 'https://kairos-anuu.onrender.com'

export async function apiFetch(path: string, options?: RequestInit) {
  const res = await fetch(`${API}${path}`, options)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export function getApiUrl(path: string) {
  return `${API}${path}`
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

export function getOrderInvoiceUrl(id: string | number) {
  return getApiUrl(`/orders/${id}/invoice`)
}

// Products / Catalog
export async function getProducts(params?: Record<string, string>) {
  const query = params ? '?' + new URLSearchParams(params).toString() : ''
  return apiFetch(`/products${query}`)
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

// Kairosdis Product Scraper
export async function scrapeKairosdis() {
  return apiFetch('/products/scrape-kairosdis', { method: 'POST' })
}

export async function getKairosdisScraperStatus() {
  return apiFetch('/products/scrape-kairosdis/status')
}

// Scraper
export async function getScraperHistory() {
  return apiFetch('/scraper/history')
}

export async function runScraper(tipo_cliente: 'lead' | 'mayorista' = 'lead') {
  return apiFetch('/scraper/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tipo_cliente }),
  })
}

export async function runEnrichment() {
  return apiFetch('/scraper/enrich', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
}

export const API_BASE = API

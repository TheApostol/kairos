import { apiFetch } from './api'

export async function getPlatformSummary() {
  return apiFetch('/platform/summary')
}

export async function getPlatformOrganizations(params?: { status?: string; customer_tier?: string; limit?: number }) {
  const query = params
    ? '?' + new URLSearchParams(
        Object.fromEntries(
          Object.entries(params)
            .filter(([, v]) => v !== undefined && v !== '')
            .map(([k, v]) => [k, String(v)])
        )
      ).toString()
    : ''
  return apiFetch(`/platform/organizations${query}`)
}

export async function createPlatformOrganization(data: Record<string, unknown>) {
  return apiFetch('/platform/organizations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function updatePlatformOrganization(id: string, data: Record<string, unknown>) {
  return apiFetch(`/platform/organizations/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function getPlatformLeadClient() {
  return apiFetch('/platform/lead-client')
}

export async function getPlatformOrgBilling(id: string) {
  return apiFetch(`/platform/organizations/${id}/billing`)
}

export async function getPlatformOrgUsage(id: string, days: number = 30) {
  return apiFetch(`/platform/organizations/${id}/usage?days=${days}`)
}

export async function getPlatformAuditLogs(params?: { organization_id?: string; action?: string; limit?: number }) {
  const query = params
    ? '?' + new URLSearchParams(
        Object.fromEntries(
          Object.entries(params)
            .filter(([, v]) => v !== undefined && v !== '')
            .map(([k, v]) => [k, String(v)])
        )
      ).toString()
    : ''
  return apiFetch(`/platform/audit-logs${query}`)
}

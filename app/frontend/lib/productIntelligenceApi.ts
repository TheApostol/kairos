import { apiFetch } from './api'

export async function checkProductOnline(data: {
  product_id?: string | number
  sku?: string
  name?: string
  brand?: string
  current_image_url?: string
}) {
  return apiFetch('/product-intelligence/check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

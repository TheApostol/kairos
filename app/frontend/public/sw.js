// Kairos CRM Service Worker
const CACHE = 'kairos-v1'
const BASE_PATH = '/dashboard'
const OFFLINE_URL = `${BASE_PATH}/admin`

// Cache these on install for offline shell
const PRECACHE = [
  `${BASE_PATH}/admin`,
  `${BASE_PATH}/leads`,
  `${BASE_PATH}/pipeline`,
  `${BASE_PATH}/manifest.json`,
]

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  )
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url)

  // Never intercept API calls — always go to network
  if (url.hostname.includes('onrender.com') || url.hostname.includes('supabase') || url.hostname === 'api.polkorp.com') return
  if (url.pathname.startsWith('/api/')) return

  // For navigation requests: network first, fallback to cache
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const copy = res.clone()
          caches.open(CACHE).then((c) => c.put(e.request, copy))
          return res
        })
        .catch(() => caches.match(e.request).then((r) => r || caches.match(OFFLINE_URL)))
    )
    return
  }

  // For static assets: cache first
  if (/\.(js|css|png|jpg|jpeg|svg|woff2?|ico)$/.test(url.pathname)) {
    e.respondWith(
      caches.match(e.request).then((cached) => {
        if (cached) return cached
        return fetch(e.request).then((res) => {
          const copy = res.clone()
          caches.open(CACHE).then((c) => c.put(e.request, copy))
          return res
        })
      })
    )
    return
  }
})

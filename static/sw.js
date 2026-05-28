const CACHE_NAME = 'elara-v3';
const CORE = [
  '/static/manifest.webmanifest',
  '/static/icon.png',
];

const SKIP_PATTERNS = [
  '/_nicegui_ws/',
  '/socket.io/',
  '/_nicegui/',
  '/api/',
  '/audio/',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  // Never cache HTML page navigations — NiceGUI must always be fetched fresh
  if (req.mode === 'navigate') return;

  const url = new URL(req.url);
  if (SKIP_PATTERNS.some((p) => url.pathname.startsWith(p))) return;

  event.respondWith(
    caches.match(req).then((cached) =>
      cached || fetch(req).then((resp) => {
        if (resp && resp.status === 200 && resp.type === 'basic') {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy)).catch(() => {});
        }
        return resp;
      })
    )
  );
});

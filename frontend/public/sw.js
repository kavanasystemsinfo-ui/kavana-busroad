/* Kavana BusRoad - Service Worker (PWA) */
const CACHE_NAME = 'busroad-v1';
const APP_SHELL = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/favicon.png',
  '/icon-192.png',
  '/icon-512.png'
];

// Instalación: cachear el app shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

// Activación: limpiar caches antiguas
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

// Fetch: red primero (la app necesita la API en vivo), fallback a caché para el shell
self.addEventListener('fetch', (event) => {
  // Solo manejar GET y URLs del mismo origen (no interceptar la API ni mapas externos)
  if (event.request.method !== 'GET' || !event.request.url.startsWith(self.location.origin)) {
    return;
  }
  // Los tiles del mapa Leaflet (openstreetmap.org) NO se cachean: van en vivo
  if (event.request.url.includes('tile.openstreetmap.org')) {
    return;
  }
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Cachear las respuestas válidas del shell
        if (response.ok && event.request.url.includes(self.location.origin)) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match('/index.html')))
  );
});

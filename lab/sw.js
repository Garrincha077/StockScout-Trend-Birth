'use strict';
const CACHE_PREFIX = 'trendbirth-install-';
const CACHE = CACHE_PREFIX + 'v1';
const assetUrl = path => new URL(path, self.registration.scope).href;
// Only install artwork and the offline screen are stored. Market data, HTML,
// app/auth scripts, callbacks and publication pointers always use the network.
const ASSETS = [
  'offline.html',
  'manifest.webmanifest',
  'icons/trendbirth.svg',
  'icons/trendbirth-192.png',
  'icons/trendbirth-512.png',
  'icons/trendbirth-maskable-512.png',
  'icons/apple-touch-icon.png'
].map(assetUrl);
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE).map(key => caches.delete(key))
  )).then(() => self.clients.claim()));
});
self.addEventListener('message', event => {
  if (event.data?.type === 'ACTIVATE_UPDATE') event.waitUntil(self.skipWaiting());
});
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(async () => {
      const cache = await caches.open(CACHE);
      const offline = await cache.match(assetUrl('offline.html'));
      // cleanUrls hosts redirect offline.html to /offline. A fresh Response
      // makes that cached page valid for navigation's manual redirect mode.
      return new Response(offline.body, {headers: offline.headers});
    }));
  } else if (ASSETS.includes(url.href)) {
    event.respondWith(caches.open(CACHE).then(cache => cache.match(request)).then(cached => cached || fetch(request)));
  }
});

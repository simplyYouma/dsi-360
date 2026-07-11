/*
 * Service worker DSI 360 — coquille applicative hors-ligne, sans jamais mettre l'API en cache.
 *
 * Stratégie, volontairement simple et sûre pour une app de données interne :
 *   - /api/**            → jamais interceptée (réseau seul, aucune mise en cache de données).
 *   - navigation (HTML)  → réseau d'abord, repli sur l'index.html en cache si hors-ligne.
 *   - ressources /assets, /icons, favicon, manifest → cache d'abord (noms hachés = immuables).
 *
 * Bump CACHE à chaque changement de cette logique : l'ancien cache est purgé à l'activation.
 */
const CACHE = 'dsi360-v1';
const COQUILLE = ['/', '/index.html', '/manifest.webmanifest', '/favicon.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(COQUILLE)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((cles) => Promise.all(cles.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

function estRessourceStatique(url) {
  return (
    url.pathname.startsWith('/assets/') ||
    url.pathname.startsWith('/icons/') ||
    url.pathname === '/favicon.png' ||
    url.pathname === '/manifest.webmanifest'
  );
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  // Même origine uniquement ; l'API n'est jamais touchée (données toujours fraîches).
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  // Navigation : réseau d'abord (toujours la dernière version), repli hors-ligne sur la coquille.
  if (req.mode === 'navigate') {
    event.respondWith(fetch(req).catch(() => caches.match('/index.html')));
    return;
  }

  // Ressources statiques immuables : cache d'abord, sinon réseau puis on met en cache.
  if (estRessourceStatique(url)) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ??
          fetch(req).then((rep) => {
            if (rep.ok) {
              const copie = rep.clone();
              caches.open(CACHE).then((c) => c.put(req, copie));
            }
            return rep;
          }),
      ),
    );
  }
});

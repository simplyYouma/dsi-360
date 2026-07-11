// Enregistre le service worker DSI 360 — uniquement en build de production.
// En dev, Vite sert la SPA avec rechargement à chaud : un service worker gênerait. Silencieux
// en cas d'échec (navigateur ancien, contexte non sécurisé) : le PWA est un plus, jamais un requis.

export function enregistrerSW(): void {
  if (!import.meta.env.PROD) return;
  if (!('serviceWorker' in navigator)) return;

  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      /* enregistrement impossible : l'application fonctionne quand même, sans hors-ligne. */
    });
  });
}

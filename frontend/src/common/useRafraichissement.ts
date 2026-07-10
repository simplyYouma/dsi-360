import { useEffect, useRef } from 'react';

/** Intervalle par défaut : assez court pour qu'un message paraisse arriver seul, assez long pour
 *  ne pas marteler l'API. */
export const INTERVALLE_DEFAUT_MS = 20_000;

/**
 * Rappelle `charger` à intervalle régulier, tant que l'onglet est visible.
 *
 * Sans cela, rien ne bouge tant que l'utilisateur ne recharge pas : une liste ouverte ignore les
 * messages qu'on lui écrit, et la cloche reste muette.
 *
 * Deux précautions qui comptent :
 *  - **En pause quand l'onglet est masqué** : un onglet oublié ne doit pas interroger le serveur
 *    toute la journée. Au retour, on rafraîchit immédiatement plutôt que d'attendre le prochain top.
 *  - **La fonction vit dans une ref** : les appelants la recréent à chaque rendu, et la mettre en
 *    dépendance relancerait la minuterie sans fin.
 *
 * @param charger  Ce qu'il faut refaire. Ni attendu, ni annulé : une passe ratée sera rejouée.
 * @param actif    Suspend le rafraîchissement (ex. pendant qu'une fiche est ouverte).
 */
export function useRafraichissement(
  charger: () => void,
  intervalleMs: number = INTERVALLE_DEFAUT_MS,
  actif = true,
): void {
  const chargerRef = useRef(charger);
  chargerRef.current = charger;

  useEffect(() => {
    if (!actif) return;

    const tick = (): void => {
      if (!document.hidden) chargerRef.current();
    };
    const minuterie = window.setInterval(tick, intervalleMs);

    // Au retour sur l'onglet, on ne fait pas attendre l'utilisateur jusqu'au prochain top.
    const surVisibilite = (): void => {
      if (!document.hidden) chargerRef.current();
    };
    document.addEventListener('visibilitychange', surVisibilite);

    return () => {
      window.clearInterval(minuterie);
      document.removeEventListener('visibilitychange', surVisibilite);
    };
  }, [intervalleMs, actif]);
}

/** Correspondance module domaine -> route front et libellé lisible.
 *  Source unique pour la recherche globale et la navigation depuis les notifications. */
export const ROUTE_MODULE: Record<string, string> = {
  incident: '/incidents',
  demande: '/demandes',
  projet: '/projets',
  changement: '/changements',
  audit: '/audit',
  risque: '/risques',
  cybersecurite: '/cybersecurite',
  gouvernance: '/gouvernance',
};

export const LIBELLE_MODULE: Record<string, string> = {
  incident: 'Incident',
  demande: 'Demande',
  projet: 'Projet',
  changement: 'Changement',
  audit: 'Audit',
  risque: 'Risque',
  cybersecurite: 'Cybersécurité',
  gouvernance: 'Gouvernance',
};

/** Lien profond vers la fiche d'une activité (ouvre la fiche à l'arrivée). */
export function lienActivite(module: string, id: string): string | null {
  const route = ROUTE_MODULE[module];
  return route === undefined ? null : `${route}?fiche=${id}`;
}

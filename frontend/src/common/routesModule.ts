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

/** Modules dont le détail est une page dédiée complète (tâches, jalons, RFC…) plutôt qu'une fiche
 *  modale : ouvrir un tel ticket doit renvoyer vers `/{route}/{id}`, pas vers la modale partielle. */
export const MODULES_PAGE_DEDIEE = new Set<string>(['projet', 'changement']);

/** Capacités de la fiche par module (miroir des flags `creer_routeur` côté backend).
 *  Source unique : garantit que la fiche ouverte depuis « Mes tickets » (multi-modules) expose
 *  exactement les mêmes fonctions que la page dédiée du module (escalade, revue, documents, type). */
export interface CapacitesModule {
  avecDocuments?: boolean;
  avecRevue?: boolean;
  gestionnaireFige?: boolean;
  moduleCategorie?: string;
  labelCategorie?: string;
}

export const CAPACITES_MODULE: Record<string, CapacitesModule> = {
  incident: { avecDocuments: true, gestionnaireFige: true, moduleCategorie: 'incident' },
  demande: { gestionnaireFige: true, moduleCategorie: 'demande' },
  changement: { avecDocuments: true, moduleCategorie: 'changement', labelCategorie: 'Type' },
  audit: { avecDocuments: true, moduleCategorie: 'audit', labelCategorie: 'Source' },
  risque: { avecRevue: true, moduleCategorie: 'risque' },
  cybersecurite: {
    avecDocuments: true,
    avecRevue: true,
    moduleCategorie: 'cybersecurite',
    labelCategorie: 'Type',
  },
  gouvernance: {
    avecDocuments: true,
    avecRevue: true,
    moduleCategorie: 'gouvernance',
    labelCategorie: 'Type',
  },
  projet: { avecDocuments: true },
};

/** Lien profond vers la fiche d'une activité (ouvre la fiche à l'arrivée). */
export function lienActivite(module: string, id: string): string | null {
  const route = ROUTE_MODULE[module];
  if (route === undefined) return null;
  // Projet & changement ont une page dédiée (tâches, jalons, RFC) : on y entre directement, plutôt
  // que d'ouvrir la fiche modale partielle sur la liste.
  return MODULES_PAGE_DEDIEE.has(module) ? `${route}/${id}` : `${route}?fiche=${id}`;
}

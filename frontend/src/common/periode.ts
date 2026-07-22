// Filtre de période partagé par les pages d'analyse (tableau de bord, analyses, tickets).
// Deux modes : un preset en nombre de jours (7/30/90/Tout), ou une plage de dates personnalisée
// choisie au calendrier — la plage prime sur le preset.

export interface Periode {
  jours: number | null; // preset : nombre de jours glissants (null = « Tout »)
  du: string | null; // borne basse ISO (yyyy-mm-dd) d'une plage personnalisée
  au: string | null; // borne haute ISO (yyyy-mm-dd) d'une plage personnalisée
}

export const PERIODE_TOUT: Periode = { jours: null, du: null, au: null };

/** Période d'ouverture des écrans d'analyse : 7 jours glissants.
 *
 *  « Tout » par défaut faisait balayer l'historique entier à chaque arrivée sur la page — des
 *  agrégations sur des années de tickets pour un premier coup d'œil qui porte, en pratique, sur
 *  la semaine. L'utilisateur élargit s'il en a besoin ; le système ne paie plus ce prix d'office. */
export const PERIODE_DEFAUT: Periode = { jours: 7, du: null, au: null };

/** Une plage de dates personnalisée est-elle active ? (elle prime sur les presets). */
export function estPerso(p: Periode): boolean {
  return p.du !== null || p.au !== null;
}

/** Paramètres de requête pour l'API (dates personnalisées prioritaires sur le nombre de jours). */
export function paramsPeriode(p: Periode): Record<string, string> {
  if (estPerso(p)) {
    const q: Record<string, string> = {};
    if (p.du !== null) q['du'] = p.du;
    if (p.au !== null) q['au'] = p.au;
    return q;
  }
  return p.jours !== null ? { jours: String(p.jours) } : {};
}

/** Suffixe `?du=…&au=…` (ou `?jours=…`, ou vide) prêt à coller à une URL d'API. */
export function requetePeriode(p: Periode): string {
  const q = new URLSearchParams(paramsPeriode(p)).toString();
  return q ? `?${q}` : '';
}

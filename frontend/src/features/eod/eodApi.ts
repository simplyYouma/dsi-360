import { api } from '@/lib/api';
import type { Permissions } from '@/common/permissions';
import { chaineFiltres, type FiltresListe } from '@/features/incidents/incidentsApi';

/** Verdict d'une étape. « Non applicable » remplace le « X » du rapport papier. */
export type StatutEtape = 'À faire' | 'En cours' | 'Complété' | 'Anomalie' | 'Non applicable';

/** « horaire » : on pointe un début et une fin. « valeur » : on relève ce qu'affiche l'écran. */
export type NatureEtape = 'horaire' | 'valeur';

export interface EtapeEod {
  id: string;
  section: string;
  libelle: string;
  nature: NatureEtape;
  aide: string | null;
  ordre: number;
  statut: StatutEtape;
  debut: string | null;
  fin: string | null;
  valeur: string | null;
  notes: string | null;
}

export interface SoireeEod {
  id: string;
  reference: string;
  titre: string;
  /** Journée comptable close — pas la date de saisie : la soirée du 15 se termine le 16. */
  journee: string | null;
  statut: string;
  categorie: string | null;
  responsable: { prenom: string; nom: string; email: string } | null;
  responsable_id: string | null;
  priorite: number | null;
  sla_resolution_le: string | null;
  statut_sla: string;
  avancement: number;
  anomalies: number;
  reste: number;
  nb_etapes: number;
  debut_effectif: string | null;
  fin_effective: string | null;
  cree_le: string;
  nb_commentaires: number;
  nb_non_vus: number;
}

export interface DetailEod extends SoireeEod {
  description: string | null;
  categorie_id: string | null;
  etapes: EtapeEod[];
  transitions_possibles: string[];
  /** Clôture que les étapes justifient, ou `null` tant qu'il reste des étapes à régler. */
  cloture_conseillee: string | null;
  permissions: Permissions;
}

export interface NouvelleSoiree {
  journee: string;
  categorie_id?: string | null;
  responsable_id?: string | null;
}

export interface MajEtape {
  statut?: StatutEtape;
  debut?: string | null;
  fin?: string | null;
  valeur?: string | null;
  notes?: string | null;
  vider_debut?: boolean;
  vider_fin?: boolean;
}

export const eodApi = {
  lister: (page: number, f?: FiltresListe): Promise<{ elements: SoireeEod[]; total: number }> =>
    api.get(`/eod?${chaineFiltres(page, f)}`),
  detail: (id: string): Promise<DetailEod> => api.get(`/eod/${id}`),
  ouvrir: (corps: NouvelleSoiree): Promise<{ id: string }> => api.post('/eod', corps),
  transition: (id: string, vers: string, note?: string): Promise<DetailEod> =>
    api.post(`/eod/${id}/transition`, { vers, note }),
  // Toutes les écritures d'étape renvoient la soirée entière : l'avancement, la clôture
  // conseillée et le compte d'anomalies changent à chaque geste. Les recalculer à l'écran, c'est
  // les voir diverger de ce que le serveur garde.
  majEtape: (id: string, etapeId: string, corps: MajEtape): Promise<DetailEod> =>
    api.patch(`/eod/${id}/etapes/${etapeId}`, corps),
  pointer: (id: string, etapeId: string, quoi: 'debut' | 'fin'): Promise<DetailEod> =>
    api.post(`/eod/${id}/etapes/${etapeId}/pointer`, { quoi }),
  ajouterEtape: (
    id: string,
    corps: { section: string; libelle: string; nature?: NatureEtape },
  ): Promise<DetailEod> => api.post(`/eod/${id}/etapes`, corps),
  supprimerEtape: (id: string, etapeId: string): Promise<DetailEod> =>
    api.del(`/eod/${id}/etapes/${etapeId}`),
  categories: (): Promise<{ id: string; code: string; libelle: string }[]> =>
    api.get('/referentiels/categories?module=eod'),
};

/** Le déroulé, coupé en sections dans l'ordre où le serveur l'a rendu.
 *
 * Partagé par l'écran et par le rapport PDF : si les deux groupaient à leur façon, une étape
 * ajoutée en cours de soirée pourrait se ranger ici et là différemment — et le document remis à
 * la hiérarchie ne montrerait plus la nuit telle qu'elle s'est pointée. */
export function grouperParSection(etapes: EtapeEod[]): { titre: string; etapes: EtapeEod[] }[] {
  const groupes: { titre: string; etapes: EtapeEod[] }[] = [];
  for (const e of etapes) {
    const dernier = groupes[groupes.length - 1];
    if (dernier !== undefined && dernier.titre === e.section) dernier.etapes.push(e);
    else groupes.push({ titre: e.section, etapes: [e] });
  }
  return groupes;
}

/** Une étape est « réglée » dès qu'elle porte un verdict — y compris « Non applicable », qui est
 *  une décision et non un oubli. C'est le compte affiché à l'écran comme au rapport. */
export function estReglee(e: EtapeEod): boolean {
  return e.statut !== 'À faire' && e.statut !== 'En cours';
}

/** « 20H29 » — la notation du rapport de la banque, et non un horodatage ISO. */
export function heure(iso: string | null): string {
  if (iso === null) return '';
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, '0')}H${String(d.getMinutes()).padStart(2, '0')}`;
}

/** « 15/09/2026 » à partir d'une date ISO (journée comptable). */
export function jour(iso: string | null): string {
  if (iso === null) return '—';
  const [a, m, j] = iso.split('-');
  return `${j}/${m}/${a}`;
}

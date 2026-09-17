import { api } from '@/lib/api';
import type { Permissions } from '@/common/permissions';
import { chaineFiltres, type FiltresListe } from '@/features/incidents/incidentsApi';

/** Verdict d'une étape. « Non applicable » remplace le « X » du rapport papier. */
export type StatutEtape = 'À faire' | 'En cours' | 'Complété' | 'Anomalie' | 'Non applicable';

/** « horaire » : on pointe un début et une fin. « valeur » : on relève ce qu'affiche l'écran. */
export type NatureEtape = 'horaire' | 'valeur';

/** « note » : ce qu'on relève en passant. « incident » : une agence a bloqué, on l'a relancée —
 *  et la forme exige alors l'agence et l'heure de relance, que le serveur refuse absentes. */
export type NatureObservation = 'note' | 'incident';

/** Une ligne du journal d'une étape. Écrite une fois pour toutes : ni correction ni suppression —
 *  une observation qui se réécrit après coup ne prouve plus rien. */
export interface ObservationEod {
  id: string;
  etape_id: string;
  nature: NatureObservation;
  agence: string | null;
  relance_le: string | null;
  texte: string;
  auteur: string | null;
  cree_le: string;
}

export interface NouvelleObservation {
  nature?: NatureObservation;
  texte: string;
  agence?: string | null;
  /** L'heure telle qu'elle se lit sur l'écran du core banking : « 01H12 ». Le serveur en déduit
   *  la journée — l'EOD franchit minuit, et la date n'est pas à retaper. */
  relance?: string | null;
}

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
  /** Le journal de l'étape, dans l'ordre où la nuit s'est vécue. */
  observations: ObservationEod[];
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
  /** Relances d'agence consignées au journal. Ne se déduit pas des anomalies : une agence peut
   *  être relancée sans que l'étape finisse en anomalie, et l'inverse existe aussi. */
  incidents: number;
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

/** Un type de soirée. Le CODE ne bouge pas (« FIN_DE_MOIS ») ; le libellé, lui, est celui que le
 *  core banking affiche (« EOM ») et se renomme depuis l'administration. C'est donc le code qui
 *  sert à raisonner — jamais le libellé. */
export interface CategorieEod {
  id: string;
  code: string;
  libelle: string;
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
  /** Observation posée **avec** le verdict, en un seul appel : « Anomalie » et « Non applicable »
   *  exigent une explication, et la demander dans un second temps ferait échouer le premier geste
   *  pour une raison que l'opérateur ne découvrirait qu'après coup. */
  observation?: NouvelleObservation;
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
  observer: (id: string, etapeId: string, corps: NouvelleObservation): Promise<DetailEod> =>
    api.post(`/eod/${id}/etapes/${etapeId}/observations`, corps),
  /** Le réseau d'agences de la banque, proposé à la saisie d'un incident — pour que « Kayes »,
   *  « AGENCE KAYES » et « Agence 11 Kayes » ne finissent pas par coexister au rapport. */
  agences: (): Promise<string[]> => api.get('/eod/agences'),
  ajouterEtape: (
    id: string,
    corps: { section: string; libelle: string; nature?: NatureEtape },
  ): Promise<DetailEod> => api.post(`/eod/${id}/etapes`, corps),
  supprimerEtape: (id: string, etapeId: string): Promise<DetailEod> =>
    api.del(`/eod/${id}/etapes/${etapeId}`),
  categories: (): Promise<CategorieEod[]> => api.get('/referentiels/categories?module=eod'),
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

/** L'heure que porte une observation : celle de la relance pour un incident, celle de l'écriture
 *  pour une note. C'est la question qu'on pose en premier — « à quelle heure ? ». */
export function heureObservation(o: ObservationEod): string {
  return heure(o.nature === 'incident' ? o.relance_le : o.cree_le);
}

/** Une observation telle qu'elle se lit dans la colonne « Observations » du rapport.
 *
 * Partagé par le PDF et par l'écran : si chacun composait sa ligne, le document remis à la
 * hiérarchie ne dirait pas tout à fait ce que l'opérateur a lu en la consignant. */
export function ligneObservation(o: ObservationEod): string {
  const tete =
    o.nature === 'incident' ? `${heureObservation(o)} · ${o.agence ?? ''}` : heureObservation(o);
  return `${tete} — ${o.texte}`;
}

/** Heure du moment, à la notation de la saisie (« 01H12 ») : l'incident se consigne sur l'instant,
 *  et l'opérateur ne doit avoir à taper que ce qu'il corrige. */
export function heureCourante(): string {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}H${String(d.getMinutes()).padStart(2, '0')}`;
}

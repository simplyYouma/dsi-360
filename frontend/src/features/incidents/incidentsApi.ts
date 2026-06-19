import { api } from '@/lib/api';

export interface ResponsableBref {
  prenom: string;
  nom: string;
  email: string;
}

export interface Incident {
  id: string;
  reference: string;
  titre: string;
  statut: string;
  priorite: number;
  categorie: string | null;
  direction: string | null;
  sla_resolution_le: string | null;
  statut_sla: 'a_lheure' | 'approche' | 'depasse';
  cree_le: string;
  responsable: ResponsableBref | null;
  demandeur: string | null;
  gestionnaire: string | null;
  responsable_id: string | null;
}

export interface PageIncidents {
  elements: Incident[];
  total: number;
  page: number;
  taille: number;
}

export interface NouvelIncident {
  titre: string;
  description: string;
  impact: number;
  urgence: number;
  demandeur: string | null;
}

export interface FiltresListe {
  statut?: string | null;
  responsable_id?: string | null;
  non_assigne?: boolean;
  q?: string | null;
  /** 'en_cours' (défaut) | 'termines' | undefined (tous) */
  etat?: string | null;
}

/** Construit la query string page + filtres (commune incidents/demandes/changements…). */
export function chaineFiltres(page: number, f?: FiltresListe): string {
  const p = new URLSearchParams({ page: String(page) });
  if (f?.statut) p.set('statut', f.statut);
  if (f?.responsable_id) p.set('responsable_id', f.responsable_id);
  if (f?.non_assigne) p.set('non_assigne', 'true');
  if (f?.q && f.q.trim() !== '') p.set('q', f.q.trim());
  if (f?.etat) p.set('etat', f.etat);
  return p.toString();
}

/** Assignation en lot, commune aux modules d'activité (base = /incidents, /demandes…). */
export function assignerLot(
  base: string,
  ids: string[],
  responsable_id: string | null,
): Promise<{ assignes: number }> {
  return api.post(`${base}/assignation-lot`, { ids, responsable_id });
}

export const incidentsApi = {
  lister: (page: number, f?: FiltresListe): Promise<PageIncidents> =>
    api.get(`/incidents?${chaineFiltres(page, f)}`),
  creer: (corps: NouvelIncident): Promise<{ id: string }> => api.post('/incidents', corps),
};

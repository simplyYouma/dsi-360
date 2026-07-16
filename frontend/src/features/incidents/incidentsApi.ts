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
  /** Compteur figé : l'activité est terminée, le SLA ne court plus (verdict à l'arrêt). */
  sla_arrete: boolean;
  cree_le: string;
  responsable: ResponsableBref | null;
  demandeur: string | null;
  gestionnaire: string | null;
  contributeur: string | null;
  responsable_id: string | null;
  nb_commentaires: number;
  nb_non_vus: number;
  /** Déduit du gestionnaire : N1/N2 s'il est des nôtres, sinon DBS (niveau 3). */
  niveau_support: number | null;
  transfere_dbs: boolean;
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
  categorie_id?: string | null;
  responsable_id?: string | null;
}

export interface CategorieRef {
  id: string;
  libelle: string;
}

export interface FiltresListe {
  statut?: string | null;
  responsable_id?: string | null;
  non_assigne?: boolean;
  /** Confiés à DBS : un gestionnaire au fichier, aucun compte chez nous (ADR-0005). */
  dbs?: boolean;
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
  if (f?.dbs) p.set('dbs', 'true');
  if (f?.q && f.q.trim() !== '') p.set('q', f.q.trim());
  if (f?.etat) p.set('etat', f.etat);
  return p.toString();
}

export const incidentsApi = {
  lister: (page: number, f?: FiltresListe): Promise<PageIncidents> =>
    api.get(`/incidents?${chaineFiltres(page, f)}`),
  creer: (corps: NouvelIncident): Promise<{ id: string }> => api.post('/incidents', corps),
  categories: (): Promise<CategorieRef[]> => api.get('/referentiels/categories?module=incident'),
};

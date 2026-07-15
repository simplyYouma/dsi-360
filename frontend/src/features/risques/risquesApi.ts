import { api } from '@/lib/api';
import {
  chaineFiltres,
  type FiltresListe,
  type CategorieRef,
} from '@/features/incidents/incidentsApi';

export interface Risque {
  id: string;
  reference: string;
  titre: string;
  statut: string;
  direction: string | null;
  responsable: { prenom: string; nom: string; email: string } | null;
  probabilite: number;
  impact: number;
  criticite: number;
  cree_le: string;
  nb_commentaires: number;
  nb_non_vus: number;
}

export interface NouveauRisque {
  titre: string;
  description: string;
  probabilite: number;
  impact: number;
  categorie_id?: string | null;
  responsable_id?: string | null;
}

export interface LienItem {
  id: string;
  libelle: string;
  url: string;
}

export const risquesApi = {
  lister: (page: number, f?: FiltresListe): Promise<{ elements: Risque[]; total: number }> =>
    api.get(`/risques?${chaineFiltres(page, f)}`),
  creer: (corps: NouveauRisque): Promise<{ id: string }> => api.post('/risques', corps),
  categories: (): Promise<CategorieRef[]> => api.get('/referentiels/categories?module=risque'),
  creerLien: (id: string, libelle: string, url: string): Promise<LienItem> =>
    api.post(`/risques/${id}/liens`, { libelle, url }),
};

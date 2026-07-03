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
}

export interface NouveauRisque {
  titre: string;
  description: string;
  probabilite: number;
  impact: number;
  categorie_id?: string | null;
  responsable_id?: string | null;
}

export const risquesApi = {
  lister: (page: number, f?: FiltresListe): Promise<{ elements: Risque[]; total: number }> =>
    api.get(`/risques?${chaineFiltres(page, f)}`),
  creer: (corps: NouveauRisque): Promise<{ id: string }> => api.post('/risques', corps),
  categories: (): Promise<CategorieRef[]> => api.get('/referentiels/categories?module=risque'),
};

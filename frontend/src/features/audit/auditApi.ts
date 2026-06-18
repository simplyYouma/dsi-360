import { api } from '@/lib/api';
import type { Incident } from '@/features/incidents/incidentsApi';
import type { Categorie } from '@/features/demandes/demandesApi';

export type Recommandation = Incident;
export type { Categorie };

export interface NouvelleRecommandation {
  titre: string;
  description: string;
  impact: number;
  urgence: number;
  categorie_id: string | null;
}

export const auditApi = {
  lister: (page: number): Promise<{ elements: Recommandation[]; total: number }> =>
    api.get(`/audit?page=${page}`),
  creer: (corps: NouvelleRecommandation): Promise<{ id: string }> => api.post('/audit', corps),
  categories: (): Promise<Categorie[]> => api.get('/referentiels/categories?module=audit'),
};

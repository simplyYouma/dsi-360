import { api } from '@/lib/api';
import type { Incident } from '@/features/incidents/incidentsApi';
import type { Categorie } from '@/features/demandes/demandesApi';

// Un changement partage la forme d'activité (priorité, catégorie = type Standard/Normal/Urgent).
export type Changement = Incident;
export type { Categorie };

export interface NouveauChangement {
  titre: string;
  description: string;
  impact: number;
  urgence: number;
  categorie_id: string | null;
}

export const changementsApi = {
  lister: (page: number): Promise<{ elements: Changement[]; total: number }> =>
    api.get(`/changements?page=${page}`),
  creer: (corps: NouveauChangement): Promise<{ id: string }> => api.post('/changements', corps),
  categories: (): Promise<Categorie[]> => api.get('/referentiels/categories?module=changement'),
};

import { api } from '@/lib/api';

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
}

export const risquesApi = {
  lister: (page: number): Promise<{ elements: Risque[]; total: number }> =>
    api.get(`/risques?page=${page}`),
  creer: (corps: NouveauRisque): Promise<{ id: string }> => api.post('/risques', corps),
};

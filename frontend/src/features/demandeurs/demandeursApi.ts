import { api } from '@/lib/api';

export interface Demandeur {
  id: string;
  nom_complet: string;
  direction: string | null;
  email: string | null;
  actif: boolean;
}

export interface PageDemandeurs {
  elements: Demandeur[];
  total: number;
  page: number;
  taille: number;
}

export interface DemandeurCorps {
  nom_complet: string;
  direction_code: string | null;
  email: string | null;
  actif?: boolean;
}

export const demandeursApi = {
  lister: (page: number, q: string): Promise<PageDemandeurs> =>
    api.get(`/demandeurs?page=${page}&q=${encodeURIComponent(q)}`),
  creer: (corps: DemandeurCorps): Promise<{ id: string }> => api.post('/demandeurs', corps),
  modifier: (id: string, corps: DemandeurCorps): Promise<void> => api.put(`/demandeurs/${id}`, corps),
  supprimer: (id: string): Promise<void> => api.del(`/demandeurs/${id}`),
};

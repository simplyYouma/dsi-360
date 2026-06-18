import { api } from '@/lib/api';

export interface Chef {
  prenom: string;
  nom: string;
  email: string;
}

export interface Projet {
  id: string;
  reference: string;
  titre: string;
  statut: string;
  direction: string | null;
  chef: Chef | null;
  avancement: number;
  date_fin: string | null;
  cree_le: string;
}

export interface PageProjets {
  elements: Projet[];
  total: number;
  page: number;
  taille: number;
}

export interface NouveauProjet {
  titre: string;
  description: string;
  sponsor: string;
  budget: number | null;
  date_debut: string | null;
  date_fin: string | null;
}

export const projetsApi = {
  lister: (page: number): Promise<PageProjets> => api.get(`/projets?page=${page}`),
  creer: (corps: NouveauProjet): Promise<{ id: string }> => api.post('/projets', corps),
};

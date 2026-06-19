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
  budget: number | null;
  date_fin: string | null;
  cree_le: string;
}

export interface PageProjets {
  elements: Projet[];
  total: number;
  page: number;
  taille: number;
}

export interface ProjetDetail extends Projet {
  description: string | null;
  sponsor: string | null;
  budget: number | null;
  date_debut: string | null;
  transitions_possibles: string[];
}

export interface NouveauProjet {
  titre: string;
  description: string;
  sponsor: string;
  budget: number | null;
  date_debut: string | null;
  date_fin: string | null;
  responsable_id: string | null;
}

export const projetsApi = {
  lister: (page: number): Promise<PageProjets> => api.get(`/projets?page=${page}`),
  creer: (corps: NouveauProjet): Promise<{ id: string }> => api.post('/projets', corps),
  detail: (id: string): Promise<ProjetDetail> => api.get(`/projets/${id}`),
  transition: (id: string, vers: string): Promise<ProjetDetail> =>
    api.post(`/projets/${id}/transition`, { vers }),
  avancement: (id: string, avancement: number): Promise<ProjetDetail> =>
    api.patch(`/projets/${id}/avancement`, { avancement }),
};

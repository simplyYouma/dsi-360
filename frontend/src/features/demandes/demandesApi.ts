import { api } from '@/lib/api';
import { chaineFiltres, type FiltresListe, type PageIncidents } from '@/features/incidents/incidentsApi';

// Une demande partage la même forme de données qu'un incident (entité Activité commune).
export type Demande = PageIncidents['elements'][number];
export type PageDemandes = PageIncidents;

export interface Categorie {
  id: string;
  code: string;
  libelle: string;
}

export interface NouvelleDemande {
  titre: string;
  description: string;
  impact: number;
  urgence: number;
  categorie_id: string | null;
}

export const demandesApi = {
  lister: (page: number, f?: FiltresListe): Promise<PageDemandes> =>
    api.get(`/demandes?${chaineFiltres(page, f)}`),
  creer: (corps: NouvelleDemande): Promise<{ id: string }> => api.post('/demandes', corps),
  categories: (): Promise<Categorie[]> => api.get('/referentiels/categories?module=demande'),
};

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
  cree_le: string;
  responsable: ResponsableBref | null;
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
}

export const incidentsApi = {
  lister: (page: number): Promise<PageIncidents> => api.get(`/incidents?page=${page}`),
  creer: (corps: NouvelIncident): Promise<{ id: string }> => api.post('/incidents', corps),
};

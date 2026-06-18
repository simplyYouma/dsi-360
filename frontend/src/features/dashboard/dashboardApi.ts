import { api } from '@/lib/api';

export interface TableauBord {
  cartes: {
    incidents_ouverts: number;
    incidents_critiques: number;
    respect_sla: number;
    demandes_en_cours: number;
    projets_en_retard: number;
    risques_critiques: number;
  };
  sla: { a_lheure: number; approche: number; depasse: number };
  repartition: { module: string; valeur: number }[];
  serie: { periode: string; a_lheure: number; approche: number; depasse: number }[];
}

export const dashboardApi = {
  charger: (): Promise<TableauBord> => api.get('/tableau-de-bord'),
};

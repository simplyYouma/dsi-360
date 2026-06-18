import { api } from '@/lib/api';

export interface AnalyseItem {
  libelle: string;
  valeur: number;
}

export interface Analyses {
  total: number;
  par_module: AnalyseItem[];
  par_direction: AnalyseItem[];
  par_responsable: AnalyseItem[];
  sla: { a_lheure: number; approche: number; depasse: number };
}

export const analysesApi = {
  charger: (): Promise<Analyses> => api.get('/analyses'),
};

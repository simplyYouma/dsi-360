import { api } from '@/lib/api';

export interface AnalyseItem {
  libelle: string;
  valeur: number;
}

export interface Kpis {
  ouvertes: number;
  respect_sla: number;
  mttr_jours: number;
  en_retard: number;
}

export interface SlaModule {
  module: string;
  a_lheure: number;
  approche: number;
  depasse: number;
}

export interface CaseRisque {
  probabilite: number;
  impact: number;
  valeur: number;
}

export interface PointTendance {
  periode: string;
  crees: number;
  resolus: number;
}

export interface Analyses {
  total: number;
  kpis: Kpis;
  par_module: AnalyseItem[];
  par_direction: AnalyseItem[];
  par_responsable: AnalyseItem[];
  par_priorite: AnalyseItem[];
  sla: { a_lheure: number; approche: number; depasse: number };
  sla_par_module: SlaModule[];
  matrice_risques: CaseRisque[];
  tendance: PointTendance[];
}

export const analysesApi = {
  charger: (): Promise<Analyses> => api.get('/analyses'),
};

import { api } from '@/lib/api';
import { requetePeriode, type Periode } from '@/common/periode';

export interface TableauBord {
  cartes: {
    incidents_ouverts: number;
    incidents_critiques: number;
    respect_sla: number;
    demandes_en_cours: number;
    projets_en_retard: number;
    risques_critiques: number;
    risques_ouverts: number;
  };
  sla: { a_lheure: number; approche: number; depasse: number };
  repartition: { module: string; valeur: number }[];
  serie: { periode: string; a_lheure: number; approche: number; depasse: number }[];
  a_traiter: {
    module: string;
    id: string;
    reference: string;
    titre: string;
    priorite: number | null;
    statut: string;
    sla_resolution_le: string;
  }[];
  /** Créations hebdomadaires (8 semaines) par module importé — miniatures des cartes. */
  creations_hebdo: Record<string, number[]>;
  dbs_ouverts: number;
  dbs_age_jours: number | null;
  rouverts_30j: number;
  resolus_30j: number;
}

export const dashboardApi = {
  charger: (periode: Periode): Promise<TableauBord> =>
    api.get(`/tableau-de-bord${requetePeriode(periode)}`),
};

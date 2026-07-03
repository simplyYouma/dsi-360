import { api } from '@/lib/api';

export interface MonTicket {
  module: string;
  id: string;
  reference: string;
  titre: string;
  statut: string;
  priorite: number | null;
  statut_sla: 'a_lheure' | 'approche' | 'depasse';
  sla_resolution_le: string | null;
  demandeur: string | null;
  cree_le: string;
  nb_commentaires: number;
}

export interface CompteLibelle {
  libelle: string;
  valeur: number;
}
export interface JourResolus {
  jour: string;
  resolus: number;
}
export interface MesStats {
  agent: { nom: string; profil: string; direction: string | null };
  ouverts: number;
  a_lheure: number;
  approche: number;
  en_retard: number;
  resolus_7j: number;
  resolus_30j: number;
  respect_sla: number;
  mttr_jours: number | null;
  plus_ancien_jours: number | null;
  par_priorite: CompteLibelle[];
  par_module: CompteLibelle[];
  par_statut: CompteLibelle[];
  tendance: JourResolus[];
}

export type SegmentTicket = 'actifs' | 'resolus' | 'termines' | 'tout';

export const mesTicketsApi = {
  lister: (segment: SegmentTicket = 'actifs'): Promise<MonTicket[]> =>
    api.get(`/mes-tickets?segment=${segment}`),
  stats: (): Promise<MesStats> => api.get('/mes-tickets/stats'),
};

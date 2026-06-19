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

export const mesTicketsApi = {
  lister: (): Promise<MonTicket[]> => api.get('/mes-tickets'),
};

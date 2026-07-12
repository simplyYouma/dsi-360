import { api } from '@/lib/api';
import { requetePeriode, type Periode } from '@/common/periode';

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
  nb_non_vus: number;
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
  resolus_periode: number;
  respect_sla: number;
  mttr_jours: number | null;
  plus_ancien_jours: number | null;
  par_priorite: CompteLibelle[];
  par_module: CompteLibelle[];
  par_statut: CompteLibelle[];
  tendance: JourResolus[];
  taches: StatsTaches;
}

export type SegmentTicket = 'actifs' | 'a_valider' | 'resolus' | 'termines' | 'tout';

export interface PageMesTickets {
  elements: MonTicket[];
  total: number;
  a_valider: number;
}

export interface StatsTaches {
  a_faire: number;
  en_cours: number;
  en_retard: number;
}

export interface PageMesTaches {
  elements: MaTache[];
  total: number;
  stats: StatsTaches;
}

export interface MaTache {
  id: string;
  titre: string;
  statut: string;
  echeance: string | null;
  cree_le: string;
  activite_id: string;
  module: string;
  reference: string;
  activite_titre: string;
  role_activite: string;
}

const q = (recherche: string): string =>
  recherche.trim() ? `&q=${encodeURIComponent(recherche.trim())}` : '';

export const mesTicketsApi = {
  lister: (segment: SegmentTicket = 'actifs', page = 1, recherche = ''): Promise<PageMesTickets> =>
    api.get(`/mes-tickets?segment=${segment}&page=${page}${q(recherche)}`),
  stats: (p: Periode): Promise<MesStats> => api.get(`/mes-tickets/stats${requetePeriode(p)}`),
  taches: (
    inclureTerminees = false,
    page = 1,
    recherche = '',
    filtre: FiltreTache = null,
  ): Promise<PageMesTaches> =>
    api.get(
      `/mes-tickets/taches?inclure_terminees=${inclureTerminees}&page=${page}${q(recherche)}` +
        (filtre ? `&filtre=${filtre}` : ''),
    ),
};

export type FiltreTache = 'a_faire' | 'en_cours' | 'en_retard' | null;

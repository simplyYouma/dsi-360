import { api } from '@/lib/api';

export interface Utilisateur {
  id: string;
  email: string;
  nom: string;
  prenom: string;
  profil: string;
  profil_libelle: string;
  direction: string | null;
  actif: boolean;
  expire_le: string | null;
  doit_changer_mdp: boolean;
}
export interface Profil {
  code: string;
  libelle: string;
}
export interface Direction {
  code: string;
  libelle: string;
}
export interface RoleAcces {
  profil: string;
  libelle: string;
  acces: string[];
}
export interface Matrice {
  modules: string[];
  roles: RoleAcces[];
}
export interface EntreeJournal {
  horodatage: string;
  acteur: string | null;
  module: string | null;
  action: string;
  cible: string | null;
}

export interface CreationUtilisateur {
  email: string;
  nom: string;
  prenom: string;
  profil_code: string;
  direction_code: string | null;
  mot_de_passe: string;
  expire_le: string | null;
}
export interface MajUtilisateur {
  nom: string;
  prenom: string;
  profil_code: string;
  direction_code: string | null;
  actif: boolean;
  expire_le: string | null;
}

export interface SlaRegle {
  priorite: number;
  prise_en_charge_minutes: number;
  resolution_minutes: number;
}

export interface MembreSupport {
  id: string;
  prenom: string;
  nom: string;
  email: string;
}
export interface GroupeSupport {
  niveau: number;
  nom: string;
  membres: MembreSupport[];
}

export const adminApi = {
  profils: (): Promise<Profil[]> => api.get('/admin/profils'),
  modulesSla: (): Promise<string[]> => api.get('/admin/sla/modules'),
  sla: (module: string): Promise<SlaRegle[]> => api.get(`/admin/sla?module=${module}`),
  definirSla: (module: string, regles: SlaRegle[]): Promise<void> =>
    api.put('/admin/sla', { module, regles }),
  directions: (): Promise<Direction[]> => api.get('/admin/directions'),
  utilisateurs: (page: number): Promise<{ elements: Utilisateur[]; total: number }> =>
    api.get(`/admin/utilisateurs?page=${page}`),
  creerUtilisateur: (corps: CreationUtilisateur): Promise<{ id: string }> =>
    api.post('/admin/utilisateurs', corps),
  modifierUtilisateur: (id: string, corps: MajUtilisateur): Promise<void> =>
    api.put(`/admin/utilisateurs/${id}`, corps),
  reinitialiserMdp: (id: string): Promise<{ mot_de_passe_temporaire: string }> =>
    api.post(`/admin/utilisateurs/${id}/reinitialiser-mdp`),
  acces: (): Promise<Matrice> => api.get('/admin/acces'),
  definirAcces: (profil: string, acces: string[]): Promise<void> =>
    api.put('/admin/acces', { profil, acces }),
  journal: (page: number): Promise<{ elements: EntreeJournal[]; total: number }> =>
    api.get(`/admin/journal?page=${page}`),
  groupesSupport: (): Promise<GroupeSupport[]> => api.get('/admin/groupes-support'),
  definirGroupeSupport: (niveau: number, utilisateur_ids: string[]): Promise<void> =>
    api.put('/admin/groupes-support', { niveau, utilisateur_ids }),
};

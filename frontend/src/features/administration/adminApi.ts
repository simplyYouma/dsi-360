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
}
export interface MajUtilisateur {
  nom: string;
  prenom: string;
  profil_code: string;
  direction_code: string | null;
  actif: boolean;
}

export interface SlaRegle {
  priorite: number;
  prise_en_charge_minutes: number;
  resolution_minutes: number;
}

export const adminApi = {
  profils: (): Promise<Profil[]> => api.get('/admin/profils'),
  sla: (): Promise<SlaRegle[]> => api.get('/admin/sla'),
  definirSla: (regles: SlaRegle[]): Promise<void> => api.put('/admin/sla', { regles }),
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
};

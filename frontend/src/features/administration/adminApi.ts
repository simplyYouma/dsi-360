import { api } from '@/lib/api';

export interface Utilisateur {
  id: string;
  email: string;
  nom: string;
  prenom: string;
  profil: string;
  profil_libelle: string;
  direction: string | null;
  niveau_support: number | null;
  actif: boolean;
  expire_le: string | null;
  doit_changer_mdp: boolean;
}
export interface Profil {
  code: string;
  libelle: string;
  /** Voit au-delà de son périmètre de direction. */
  transverse: boolean;
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
  niveau_support: number | null;
  expire_le: string | null;
}
export interface MajUtilisateur {
  nom: string;
  prenom: string;
  profil_code: string;
  direction_code: string | null;
  niveau_support: number | null;
  actif: boolean;
  expire_le: string | null;
}

export interface SlaRegle {
  priorite: number;
  prise_en_charge_minutes: number;
  resolution_minutes: number;
}

export const adminApi = {
  profils: (): Promise<Profil[]> => api.get('/admin/profils'),
  /** Le code technique est dérivé du libellé côté serveur : on nomme, on ne code pas. */
  creerProfil: (libelle: string, transverse: boolean): Promise<Profil> =>
    api.post('/admin/profils', { libelle, transverse }),
  modifierProfil: (code: string, libelle: string, transverse: boolean): Promise<Profil> =>
    api.patch(`/admin/profils/${code}`, { libelle, transverse }),
  supprimerProfil: (code: string): Promise<void> => api.del(`/admin/profils/${code}`),
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
  reinitialiserMdp: (id: string): Promise<{ email: string }> =>
    api.post(`/admin/utilisateurs/${id}/reinitialiser-mdp`),
  acces: (): Promise<Matrice> => api.get('/admin/acces'),
  definirAcces: (profil: string, acces: string[]): Promise<void> =>
    api.put('/admin/acces', { profil, acces }),
  journal: (page: number): Promise<{ elements: EntreeJournal[]; total: number }> =>
    api.get(`/admin/journal?page=${page}`),
};

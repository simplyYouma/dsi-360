import { api } from '@/lib/api';

export interface Utilisateur {
  id: string;
  email: string;
  nom: string;
  prenom: string;
  profil: string;
  profil_libelle: string;
  direction: string | null;
  matricule: string | null;
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
  /** Département auquel le profil appartient. `null` pour un profil transverse, qui n'en a aucun. */
  departement_id: string | null;
  departement: string | null;
}
export interface Departement {
  id: string;
  code: string;
  libelle: string;
  direction: string;
  /** Profils rattachés : la suppression est refusée tant qu'il y en a. */
  nb_profils: number;
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
  matricule: string | null;
  niveau_support: number | null;
  expire_le: string | null;
}
export interface MajUtilisateur {
  nom: string;
  prenom: string;
  profil_code: string;
  direction_code: string | null;
  matricule: string | null;
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
  /** `direction` ne garde que les profils de cette direction — plus les transverses, toujours. */
  profils: (direction?: string | null): Promise<Profil[]> =>
    api.get(direction ? `/admin/profils?direction=${encodeURIComponent(direction)}` : '/admin/profils'),
  /** Le code technique est dérivé du libellé côté serveur : on nomme, on ne code pas. */
  creerProfil: (libelle: string, transverse: boolean): Promise<Profil> =>
    api.post('/admin/profils', { libelle, transverse }),
  /** `departement_id` omis = inchangé ; `null` explicite = détacher. */
  modifierProfil: (
    code: string,
    corps: { libelle: string; transverse?: boolean; departement_id?: string | null },
  ): Promise<Profil> => api.patch(`/admin/profils/${code}`, corps),
  supprimerProfil: (code: string): Promise<void> => api.del(`/admin/profils/${code}`),
  departements: (): Promise<Departement[]> => api.get('/admin/departements'),
  creerDepartement: (libelle: string): Promise<Departement> =>
    api.post('/admin/departements', { libelle }),
  renommerDepartement: (id: string, libelle: string): Promise<Departement> =>
    api.patch(`/admin/departements/${id}`, { libelle }),
  supprimerDepartement: (id: string): Promise<void> => api.del(`/admin/departements/${id}`),
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
  journal: (
    page: number,
    f?: { q?: string; module?: string | null; action?: string | null },
  ): Promise<{ elements: EntreeJournal[]; total: number }> => {
    const p = new URLSearchParams({ page: String(page) });
    if (f?.q && f.q.trim() !== '') p.set('q', f.q.trim());
    if (f?.module) p.set('module', f.module);
    if (f?.action) p.set('action', f.action);
    return api.get(`/admin/journal?${p.toString()}`);
  },
  /** Modules et actions réellement présents : les filtres ne proposent que ce qui existe. */
  journalReferentiels: (): Promise<{ modules: string[]; actions: string[] }> =>
    api.get('/admin/journal/referentiels'),
};

import { api, televerser } from '@/lib/api';

export interface RapportImport {
  total: number;
  incidents: number;
  demandes: number;
  crees: number;
  mis_a_jour: number;
  inchanges: number;
  demandeurs_crees: number;
  gestionnaires_crees: number;
}

export interface RapportImportEquipements {
  total: number;
  crees: number;
  mis_a_jour: number;
  /** Lignes sans code d'immobilisation : impossible de les reconnaître d'un import à l'autre. */
  ignores: number;
  /** Matricules nommés par le fichier qu'aucun compte ne porte : rattachements à faire. */
  detenteurs_non_rapproches: number;
  /** Lignes portant un état constaté — exploité par les campagnes d'inventaire. */
  avec_etat_constate: number;
}

export const importApi = {
  tickets: (fichier: File): Promise<RapportImport> => televerser('/import/tickets', fichier),
  equipements: (fichier: File): Promise<RapportImportEquipements> =>
    televerser('/import/equipements', fichier),
  /** Dépôt unique : le serveur reconnaît le fichier (tickets ou inventaire) à ses en-têtes. */
  fichier: (fichier: File): Promise<RapportFichier> => televerser('/import/fichier', fichier),
};

export interface DernierImport {
  nature: 'tickets' | 'equipements' | string;
  horodatage: string;
  acteur: string | null;
  /** Compte-rendu tel que journalisé (créés, mis à jour…) — les clés varient selon la nature. */
  details: Record<string, number>;
}

/** Compte-rendu du dépôt unifié : la nature est reconnue par le serveur, à ses en-têtes. */
export type RapportFichier =
  ({ nature: 'tickets' } & RapportImport) | ({ nature: 'equipements' } & RapportImportEquipements);

export const etatImports = (): Promise<{ derniers: DernierImport[] }> => api.get('/import/etat');

import { televerser } from '@/lib/api';

export interface RapportImport {
  total: number;
  incidents: number;
  demandes: number;
  crees: number;
  mis_a_jour: number;
  demandeurs_crees: number;
  gestionnaires_crees: number;
}

export const importApi = {
  tickets: (fichier: File): Promise<RapportImport> => televerser('/import/tickets', fichier),
};

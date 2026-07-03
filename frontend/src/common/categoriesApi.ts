import { api } from '@/lib/api';
import type { CategorieRef } from '@/features/incidents/incidentsApi';

/** Gestion des catégories (paramétrage — réservé aux profils Administration côté serveur). */
export const categoriesApi = {
  creer: (module: string, libelle: string): Promise<CategorieRef> =>
    api.post('/admin/categories', { module, libelle }),
  supprimer: (id: string): Promise<void> => api.del(`/admin/categories/${id}`),
};

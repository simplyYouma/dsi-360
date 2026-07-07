import { api } from '@/lib/api';

export interface Commentaire {
  id: number;
  auteur: string;
  texte: string;
  cree_le: string;
}

/** Fil de discussion d'une activité, ou d'une tâche précise si `tacheId` est fourni. */
export const commentairesApi = {
  lister: (activiteId: string, tacheId?: string): Promise<Commentaire[]> =>
    api.get(`/commentaires/${activiteId}${tacheId ? `?tache=${tacheId}` : ''}`),
  ajouter: (activiteId: string, texte: string, tacheId?: string): Promise<Commentaire> =>
    api.post(`/commentaires/${activiteId}${tacheId ? `?tache=${tacheId}` : ''}`, { texte }),
};

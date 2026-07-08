import { api } from '@/lib/api';

export interface Commentaire {
  id: number;
  auteur: string;
  auteur_id: string | null;
  texte: string;
  cree_le: string;
  edite: boolean;
}

/** Fil de discussion d'une activité, ou d'une tâche précise si `tacheId` est fourni. */
export const commentairesApi = {
  lister: (activiteId: string, tacheId?: string): Promise<Commentaire[]> =>
    api.get(`/commentaires/${activiteId}${tacheId ? `?tache=${tacheId}` : ''}`),
  ajouter: (
    activiteId: string,
    texte: string,
    tacheId?: string,
    mentions: string[] = [],
  ): Promise<Commentaire> =>
    api.post(`/commentaires/${activiteId}${tacheId ? `?tache=${tacheId}` : ''}`, {
      texte,
      mentions,
    }),
  modifier: (commentaireId: number, texte: string): Promise<Commentaire> =>
    api.patch(`/commentaires/msg/${commentaireId}`, { texte }),
  supprimer: (commentaireId: number): Promise<void> =>
    api.del(`/commentaires/msg/${commentaireId}`),
};

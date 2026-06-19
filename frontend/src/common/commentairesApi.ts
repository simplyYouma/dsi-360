import { api } from '@/lib/api';

export interface Commentaire {
  id: number;
  auteur: string;
  texte: string;
  cree_le: string;
}

export const commentairesApi = {
  lister: (activiteId: string): Promise<Commentaire[]> => api.get(`/commentaires/${activiteId}`),
  ajouter: (activiteId: string, texte: string): Promise<Commentaire> =>
    api.post(`/commentaires/${activiteId}`, { texte }),
};

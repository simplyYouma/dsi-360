import { api, envoyerFormulaire, recupererBlob } from '@/lib/api';

export interface ImageCommentaire {
  id: string;
  nom: string;
  type_mime: string;
  largeur: number | null;
  hauteur: number | null;
}

export interface Commentaire {
  id: number;
  auteur: string;
  auteur_id: string | null;
  texte: string;
  cree_le: string;
  edite: boolean;
  nb_vues: number;
  vu: boolean;
  images: ImageCommentaire[];
}

export interface LecteurCommentaire {
  nom: string;
  vu_le: string;
}

const suffixeTache = (tacheId?: string): string => (tacheId ? `?tache=${tacheId}` : '');

/** Fil de discussion d'une activité, ou d'une tâche précise si `tacheId` est fourni. */
export const commentairesApi = {
  lister: (activiteId: string, tacheId?: string): Promise<Commentaire[]> =>
    api.get(`/commentaires/${activiteId}${suffixeTache(tacheId)}`),
  ajouter: (
    activiteId: string,
    texte: string,
    tacheId?: string,
    mentions: string[] = [],
  ): Promise<Commentaire> =>
    api.post(`/commentaires/${activiteId}${suffixeTache(tacheId)}`, { texte, mentions }),
  /** Message accompagné d'images (captures) : message et images en une seule transaction. */
  ajouterAvecImages: (
    activiteId: string,
    texte: string,
    images: File[],
    tacheId?: string,
    mentions: string[] = [],
  ): Promise<Commentaire> => {
    const corps = new FormData();
    corps.append('texte', texte);
    corps.append('mentions', mentions.join(','));
    for (const img of images) corps.append('fichiers', img);
    return envoyerFormulaire(`/commentaires/${activiteId}/images${suffixeTache(tacheId)}`, corps);
  },
  /** Octets d'une image du fil (l'accès est contrôlé : on passe par le jeton, pas par une URL nue). */
  image: (commentaireId: number, imageId: string): Promise<Blob> =>
    recupererBlob(`/commentaires/msg/${commentaireId}/images/${imageId}`),
  modifier: (commentaireId: number, texte: string): Promise<Commentaire> =>
    api.patch(`/commentaires/msg/${commentaireId}`, { texte }),
  supprimer: (commentaireId: number): Promise<void> =>
    api.del(`/commentaires/msg/${commentaireId}`),
  /** Marque tout le fil comme lu par l'utilisateur connecté. */
  marquerVues: (activiteId: string, tacheId?: string): Promise<void> =>
    api.post(`/commentaires/${activiteId}/vues${suffixeTache(tacheId)}`),
  lecteurs: (commentaireId: number): Promise<LecteurCommentaire[]> =>
    api.get(`/commentaires/msg/${commentaireId}/vues`),
};

import { api, televerser, telecharger, recupererBlob } from '@/lib/api';
import { chaineFiltres, type FiltresListe } from '@/features/incidents/incidentsApi';
import { STATUTS_TACHE } from '@/common/tacheTypes';
import type { Permissions } from '@/common/permissions';
import type { StatutTache, Tache, NouvelleTache, MajTache } from '@/common/tacheTypes';

export interface Chef {
  prenom: string;
  nom: string;
  email: string;
}

export interface Projet {
  id: string;
  reference: string;
  titre: string;
  statut: string;
  direction: string | null;
  chef: Chef | null;
  responsable_id: string | null;
  avancement: number;
  budget: number | null;
  date_fin: string | null;
  cree_le: string;
}

export interface PageProjets {
  elements: Projet[];
  total: number;
  page: number;
  taille: number;
}

export interface ProjetDetail extends Projet {
  description: string | null;
  sponsor: string | null;
  budget: number | null;
  date_debut: string | null;
  transitions_possibles: string[];
  /** Ce que l'appelant peut faire ici, calculé par le serveur. */
  permissions: Permissions;
}

export interface NouveauProjet {
  titre: string;
  description: string;
  sponsor: string;
  budget: number | null;
  date_debut: string | null;
  date_fin: string | null;
  responsable_id: string | null;
}

export interface DocumentItem {
  id: string;
  nom: string;
  type_mime: string;
  taille: number;
  depose_par: string | null;
  depose_le: string;
}

export { STATUTS_TACHE };
export type { StatutTache, Tache, NouvelleTache, MajTache };

export interface Jalon {
  id: string;
  titre: string;
  echeance: string | null;
  atteint: boolean;
  ordre: number;
}

export interface Note {
  id: string;
  texte: string;
  contexte: string | null;
  auteur: string | null;
  cree_le: string;
}

export interface Lien {
  id: string;
  libelle: string;
  url: string;
  cree_le: string;
}

export const projetsApi = {
  lister: (page: number, f?: FiltresListe): Promise<PageProjets> =>
    api.get(`/projets?${chaineFiltres(page, f)}`),
  creer: (corps: NouveauProjet): Promise<{ id: string }> => api.post('/projets', corps),
  detail: (id: string): Promise<ProjetDetail> => api.get(`/projets/${id}`),
  modifier: (id: string, corps: Partial<NouveauProjet>): Promise<ProjetDetail> =>
    api.patch(`/projets/${id}`, corps),
  transition: (id: string, vers: string, note?: string): Promise<ProjetDetail> =>
    api.post(`/projets/${id}/transition`, { vers, note: note ?? null }),
  // Journal de bord (notes) & liens utiles.
  notes: (id: string): Promise<Note[]> => api.get(`/projets/${id}/notes`),
  creerNote: (id: string, texte: string): Promise<Note> =>
    api.post(`/projets/${id}/notes`, { texte }),
  liens: (id: string): Promise<Lien[]> => api.get(`/projets/${id}/liens`),
  creerLien: (id: string, libelle: string, url: string): Promise<Lien> =>
    api.post(`/projets/${id}/liens`, { libelle, url }),
  supprimerLien: (id: string, lienId: string): Promise<void> =>
    api.del(`/projets/${id}/liens/${lienId}`),
  // Tâches (l'avancement et le passage « En cours » se déduisent des tâches, côté serveur).
  taches: (id: string): Promise<Tache[]> => api.get(`/projets/${id}/taches`),
  creerTache: (id: string, corps: NouvelleTache): Promise<ProjetDetail> =>
    api.post(`/projets/${id}/taches`, corps),
  majTache: (id: string, tacheId: string, corps: MajTache): Promise<ProjetDetail> =>
    api.patch(`/projets/${id}/taches/${tacheId}`, corps),
  supprimerTache: (id: string, tacheId: string): Promise<ProjetDetail> =>
    api.del(`/projets/${id}/taches/${tacheId}`),
  reordonnerTaches: (id: string, ordre: string[]): Promise<ProjetDetail> =>
    api.patch(`/projets/${id}/taches`, { ordre }),
  jalons: (id: string): Promise<Jalon[]> => api.get(`/projets/${id}/jalons`),
  creerJalon: (id: string, corps: { titre: string; echeance?: string | null }): Promise<Jalon> =>
    api.post(`/projets/${id}/jalons`, corps),
  majJalon: (
    id: string,
    jalonId: string,
    corps: Partial<{ titre: string; echeance: string | null; atteint: boolean }>,
  ): Promise<Jalon> => api.patch(`/projets/${id}/jalons/${jalonId}`, corps),
  supprimerJalon: (id: string, jalonId: string): Promise<void> =>
    api.del(`/projets/${id}/jalons/${jalonId}`),
  documents: (id: string): Promise<DocumentItem[]> => api.get(`/projets/${id}/documents`),
  deposerDocument: (id: string, fichier: File): Promise<DocumentItem> =>
    televerser(`/projets/${id}/documents`, fichier),
  documentsTache: (id: string, tacheId: string): Promise<DocumentItem[]> =>
    api.get(`/projets/${id}/taches/${tacheId}/documents`),
  deposerDocumentTache: (id: string, tacheId: string, fichier: File): Promise<DocumentItem> =>
    televerser(`/projets/${id}/taches/${tacheId}/documents`, fichier),
  telechargerDocument: (id: string, docId: string): Promise<void> =>
    telecharger(`/projets/${id}/documents/${docId}`),
  apercuDocument: (id: string, docId: string): Promise<Blob> =>
    recupererBlob(`/projets/${id}/documents/${docId}`),
  vignetteDocument: (id: string, docId: string): Promise<Blob> =>
    recupererBlob(`/projets/${id}/documents/${docId}?taille=vignette`),
  renommerDocument: (id: string, docId: string, nom: string): Promise<DocumentItem> =>
    api.patch(`/projets/${id}/documents/${docId}`, { nom }),
  supprimerDocument: (id: string, docId: string): Promise<void> =>
    api.del(`/projets/${id}/documents/${docId}`),
};

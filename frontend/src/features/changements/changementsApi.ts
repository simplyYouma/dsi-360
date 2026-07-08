import { api, televerser, telecharger, recupererBlob } from '@/lib/api';
import { chaineFiltres, type FiltresListe, type Incident } from '@/features/incidents/incidentsApi';
import type { Categorie } from '@/features/demandes/demandesApi';
import type { MajTache, NouvelleTache, Tache } from '@/common/tacheTypes';
import type { NoteJournal } from '@/common/JournalNotes';
import type { LienItem } from '@/common/LiensTache';
import type { DocumentItem } from '@/features/projets/projetsApi';

// Un changement partage la forme d'activité (priorité, catégorie = type Standard/Normal/Urgent).
export type Changement = Incident;
export type { Categorie };

export interface Contributeur {
  id: string;
  prenom: string;
  nom: string;
  email: string;
  decision?: string | null;
}

export interface ChangementDetail {
  id: string;
  reference: string;
  titre: string;
  statut: string;
  description: string | null;
  priorite: number;
  categorie: string | null;
  categorie_id: string | null;
  statut_sla?: 'a_lheure' | 'approche' | 'depasse';
  sla_resolution_le: string | null;
  cree_le: string;
  responsable: { prenom: string; nom: string } | null;
  responsable_id: string | null;
  demandeur: string | null;
  transitions_possibles: string[];
  etats: string[];
  historique: { statut: string; horodatage: string; acteur: string | null }[];
  contributeurs: Contributeur[];
  valideurs: Contributeur[];
  avancement: number;
  // Champs RFC (ITIL SI-12.04) — null si non renseignés.
  analyse_impact: string | null;
  analyse_risque: string | null;
  plan_deploiement: string | null;
  plan_retour_arriere: string | null;
  bilan_post_implementation: string | null;
}

export type ChangementMaj = Partial<{
  titre: string;
  description: string | null;
  analyse_impact: string | null;
  analyse_risque: string | null;
  plan_deploiement: string | null;
  plan_retour_arriere: string | null;
  bilan_post_implementation: string | null;
}>;

export interface NouveauChangement {
  titre: string;
  description: string;
  impact: number;
  urgence: number;
  categorie_id: string | null;
  responsable_id?: string | null;
}

const B = '/changements';

export const changementsApi = {
  lister: (page: number, f?: FiltresListe): Promise<{ elements: Changement[]; total: number }> =>
    api.get(`${B}?${chaineFiltres(page, f)}`),
  creer: (corps: NouveauChangement): Promise<{ id: string }> => api.post(B, corps),
  categories: (): Promise<Categorie[]> => api.get('/referentiels/categories?module=changement'),
  detail: (id: string): Promise<ChangementDetail> => api.get(`${B}/${id}`),
  modifier: (id: string, corps: ChangementMaj): Promise<ChangementDetail> =>
    api.patch(`${B}/${id}`, corps),
  changerType: (id: string, categorie_id: string | null): Promise<ChangementDetail> =>
    api.post(`${B}/${id}/categorie`, { categorie_id }),
  transition: (id: string, vers: string): Promise<ChangementDetail> =>
    api.post(`${B}/${id}/transition`, { vers }),
  assigner: (id: string, responsable_id: string | null): Promise<ChangementDetail> =>
    api.post(`${B}/${id}/assignation`, { responsable_id }),
  ajouterContributeur: (id: string, utilisateur_id: string): Promise<ChangementDetail> =>
    api.post(`${B}/${id}/contributeurs`, { utilisateur_id }),
  retirerContributeur: (id: string, uid: string): Promise<ChangementDetail> =>
    api.del(`${B}/${id}/contributeurs/${uid}`),
  ajouterValideur: (id: string, utilisateur_id: string): Promise<ChangementDetail> =>
    api.post(`${B}/${id}/valideurs`, { utilisateur_id }),
  retirerValideur: (id: string, uid: string): Promise<ChangementDetail> =>
    api.del(`${B}/${id}/valideurs/${uid}`),
  decider: (id: string, decision: 'APPROUVE' | 'REJETE'): Promise<ChangementDetail> =>
    api.post(`${B}/${id}/decision`, { decision }),
  taches: (id: string): Promise<Tache[]> => api.get(`${B}/${id}/taches`),
  creerTache: (id: string, corps: NouvelleTache): Promise<ChangementDetail> =>
    api.post(`${B}/${id}/taches`, corps),
  majTache: (id: string, tacheId: string, corps: MajTache): Promise<ChangementDetail> =>
    api.patch(`${B}/${id}/taches/${tacheId}`, corps),
  supprimerTache: (id: string, tacheId: string): Promise<ChangementDetail> =>
    api.del(`${B}/${id}/taches/${tacheId}`),
  // Pièces jointes (niveau changement + par tâche) — mêmes routes que les projets.
  documents: (id: string): Promise<DocumentItem[]> => api.get(`${B}/${id}/documents`),
  deposerDocument: (id: string, fichier: File): Promise<DocumentItem> =>
    televerser(`${B}/${id}/documents`, fichier),
  documentsTache: (id: string, tacheId: string): Promise<DocumentItem[]> =>
    api.get(`${B}/${id}/taches/${tacheId}/documents`),
  deposerDocumentTache: (id: string, tacheId: string, fichier: File): Promise<DocumentItem> =>
    televerser(`${B}/${id}/taches/${tacheId}/documents`, fichier),
  telechargerDocument: (id: string, docId: string): Promise<void> =>
    telecharger(`${B}/${id}/documents/${docId}`),
  apercuDocument: (id: string, docId: string): Promise<Blob> =>
    recupererBlob(`${B}/${id}/documents/${docId}`),
  renommerDocument: (id: string, docId: string, nom: string): Promise<DocumentItem> =>
    api.patch(`${B}/${id}/documents/${docId}`, { nom }),
  supprimerDocument: (id: string, docId: string): Promise<void> =>
    api.del(`${B}/${id}/documents/${docId}`),
  // Journal de bord (notes horodatées) — mêmes routes que les projets.
  notes: (id: string): Promise<NoteJournal[]> => api.get(`${B}/${id}/notes`),
  creerNote: (id: string, texte: string): Promise<NoteJournal> =>
    api.post(`${B}/${id}/notes`, { texte }),
  // Liens utiles d'une tâche — mêmes routes que les projets.
  liensTache: (id: string, tacheId: string): Promise<LienItem[]> =>
    api.get(`${B}/${id}/liens?tache=${tacheId}`),
  creerLienTache: (id: string, tacheId: string, libelle: string, url: string): Promise<LienItem> =>
    api.post(`${B}/${id}/liens?tache=${tacheId}`, { libelle, url }),
  supprimerLien: (id: string, lienId: string): Promise<void> =>
    api.del(`${B}/${id}/liens/${lienId}`),
};

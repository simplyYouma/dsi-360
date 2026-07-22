import { api } from '@/lib/api';

export interface Equipement {
  id: string;
  code_immo: string | null;
  numero_serie: string | null;
  modele: string | null;
  designation: string;
  emplacement: string | null;
  departement: string | null;
  /** Nom du détenteur si son matricule a été rapproché d'un compte. */
  detenteur: string | null;
  matricule: string | null;
  date_acquisition: string | null;
  valeur_acquisition: number | null;
  /** Valeur nette comptable, calculée par le serveur — jamais stockée. */
  valeur_nette: number | null;
  amorti_pct: number | null;
  actif: boolean;
}

export interface EquipementDetail extends Equipement {
  emplacement_id: string | null;
  departement_id: string | null;
  detenteur_id: string | null;
  taux: number | null;
  duree_annees: number | null;
  source: string;
  dotation_annuelle: number | null;
  amortissement_cumule: number | null;
  fin_amortissement: string | null;
  totalement_amorti: boolean;
  /** Le taux et la durée du fichier se contredisent : donnée à vérifier. */
  amortissement_incoherent: boolean;
}

export interface StatsInventaire {
  total: number;
  en_service: number;
  sortis: number;
  sans_detenteur: number;
  valeur_acquisition: number;
}

export interface ReferentielItem {
  id: string;
  libelle: string;
  actif: boolean;
}

export interface FiltresInventaire {
  q?: string | null;
  emplacement_id?: string | null;
  departement_id?: string | null;
  detenteur_id?: string | null;
  /** `false` pour voir ce qui est sorti du parc, `null` pour tout. */
  actif?: boolean | null;
}

export interface NouvelEquipement {
  designation: string;
  code_immo?: string | null;
  numero_serie?: string | null;
  modele?: string | null;
  emplacement_id?: string | null;
  departement_id?: string | null;
  detenteur_id?: string | null;
  taux?: number | null;
  date_acquisition?: string | null;
  duree_annees?: number | null;
  valeur_acquisition?: number | null;
}

export type MajEquipement = Partial<NouvelEquipement> & { actif?: boolean };

function chaineFiltres(page: number, f?: FiltresInventaire): string {
  const p = new URLSearchParams({ page: String(page) });
  if (f?.q && f.q.trim() !== '') p.set('q', f.q.trim());
  if (f?.emplacement_id) p.set('emplacement_id', f.emplacement_id);
  if (f?.departement_id) p.set('departement_id', f.departement_id);
  if (f?.detenteur_id) p.set('detenteur_id', f.detenteur_id);
  // `actif` non transmis = tout le parc ; sinon on précise l'état voulu.
  if (f?.actif !== null && f?.actif !== undefined) p.set('actif', String(f.actif));
  return p.toString();
}

export const inventaireApi = {
  lister: (
    page: number,
    f?: FiltresInventaire,
  ): Promise<{ elements: Equipement[]; total: number }> =>
    api.get(`/inventaire?${chaineFiltres(page, f)}`),
  detail: (id: string): Promise<EquipementDetail> => api.get(`/inventaire/${id}`),
  creer: (corps: NouvelEquipement): Promise<EquipementDetail> => api.post('/inventaire', corps),
  modifier: (id: string, corps: MajEquipement): Promise<EquipementDetail> =>
    api.patch(`/inventaire/${id}`, corps),
  supprimer: (id: string): Promise<void> => api.del(`/inventaire/${id}`),
  referentiel: (cle: 'emplacements' | 'departements'): Promise<ReferentielItem[]> =>
    api.get(`/inventaire/referentiels/${cle}`),
  ajouterReferentiel: (
    cle: 'emplacements' | 'departements',
    libelle: string,
  ): Promise<ReferentielItem> => api.post(`/inventaire/referentiels/${cle}`, { libelle }),
};

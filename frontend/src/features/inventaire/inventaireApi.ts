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
  /** Dernier contrôle de terrain. `null` n'est pas un verdict : personne n'y est allé. */
  etat_constate: string | null;
  constate_le: string | null;
  constate_par: string | null;
  constat_motif: string | null;
}

export interface EvenementEquipement {
  action: string;
  horodatage: string;
  acteur: string | null;
  /** Ce qui a changé, en clair (« emplacement : Siège → Agence Kayes ») : l'acheminement. */
  detail: string | null;
}

export interface EquipementDetail extends Equipement {
  /** Dernières actions journalisées (création, modifications, import), plus récentes d'abord. */
  historique: EvenementEquipement[];
  emplacement_id: string | null;
  departement_id: string | null;
  detenteur_id: string | null;
  /** Nom libre quand le détenteur n'a pas de compte (agence, prestataire). */
  detenteur_externe: string | null;
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
  /** État constaté du parc en service. */
  bons: number;
  rebuts: number;
  casses: number;
  /** Jamais contrôlés, ou pas depuis plus d'un an : le travail de terrain qui attend. */
  a_controler: number;
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
  /** Dernier état constaté (BON, REBUT, CASSE). */
  etat_constate?: string | null;
  /** Jamais contrôlé, ou pas depuis plus d'un an : la liste de travail du terrain. */
  a_controler?: boolean;
}

export interface NouvelEquipement {
  designation: string;
  code_immo?: string | null;
  numero_serie?: string | null;
  modele?: string | null;
  emplacement_id?: string | null;
  departement_id?: string | null;
  detenteur_id?: string | null;
  /** Détenteur sans compte : saisi librement, exclusif avec `detenteur_id`. */
  detenteur_externe?: string | null;
  taux?: number | null;
  date_acquisition?: string | null;
  duree_annees?: number | null;
  valeur_acquisition?: number | null;
}

export type MajEquipement = Partial<NouvelEquipement> & { actif?: boolean };

/** Ce qu'un agent peut constater sur le terrain. */
export type EtatConstat = 'BON' | 'REBUT' | 'CASSE';

/** Les trois constats et leur couleur — partagés entre la liste et la fiche. */
export const CONSTATS: { etat: EtatConstat; libelle: string; couleur: string }[] = [
  { etat: 'BON', libelle: 'Bon', couleur: 'var(--status-ok)' },
  { etat: 'REBUT', libelle: 'Rebut', couleur: 'var(--status-warn)' },
  { etat: 'CASSE', libelle: 'Cassé', couleur: 'var(--status-danger)' },
];

export const COULEUR_ETAT: Record<string, string> = {
  BON: 'var(--status-ok)',
  REBUT: 'var(--status-warn)',
  CASSE: 'var(--status-danger)',
};

export const LIBELLE_ETAT: Record<string, string> = {
  BON: 'Bon',
  REBUT: 'Rebut',
  CASSE: 'Cassé',
};

export interface TrancheParc {
  libelle: string;
  nombre: number;
  valeur_acquisition: number;
  valeur_nette: number;
}

export interface AnalysesParc {
  parc_actif: number;
  valeur_acquisition: number;
  valeur_nette: number;
  totalement_amortis: number;
  sans_donnee_comptable: number;
  par_emplacement: TrancheParc[];
  par_departement: TrancheParc[];
  par_age: TrancheParc[];
}

function chaineFiltres(page: number, f?: FiltresInventaire): string {
  const p = new URLSearchParams({ page: String(page) });
  if (f?.q && f.q.trim() !== '') p.set('q', f.q.trim());
  if (f?.emplacement_id) p.set('emplacement_id', f.emplacement_id);
  if (f?.departement_id) p.set('departement_id', f.departement_id);
  if (f?.detenteur_id) p.set('detenteur_id', f.detenteur_id);
  // `actif` non transmis = tout le parc ; sinon on précise l'état voulu.
  if (f?.actif !== null && f?.actif !== undefined) p.set('actif', String(f.actif));
  if (f?.etat_constate) p.set('etat_constate', f.etat_constate);
  if (f?.a_controler === true) p.set('a_controler', 'true');
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
  analyses: (): Promise<AnalysesParc> => api.get('/inventaire/analyses'),
  /** Consigner ce qu'on a vu du matériel. Ouvert à tout agent du module, contrairement au
   *  reste de la fiche : contrôler le parc est un travail de terrain. */
  constater: (
    id: string,
    etat: EtatConstat,
    justification: string,
  ): Promise<EquipementDetail> =>
    api.put(`/inventaire/${id}/constat`, { etat, justification }),
  retirerConstat: (id: string): Promise<EquipementDetail> =>
    api.del(`/inventaire/${id}/constat`),
};

import { api } from '@/lib/api';
import { requetePeriode, type Periode } from '@/common/periode';

export interface AnalyseItem {
  libelle: string;
  valeur: number;
}

export interface Kpis {
  ouvertes: number;
  respect_sla: number;
  mttr_jours: number;
  en_retard: number;
}

export interface SlaModule {
  module: string;
  a_lheure: number;
  approche: number;
  depasse: number;
}

export interface CaseRisque {
  probabilite: number;
  impact: number;
  valeur: number;
}

export interface PointTendance {
  periode: string;
  crees: number;
  resolus: number;
}

export interface SlaPriorite {
  priorite: string;
  dans_delai: number;
  total: number;
  taux: number;
}

export interface PointActivite {
  jour: number; // 1 = lundi … 7 = dimanche
  heure: number;
  valeur: number;
}

export interface DureeStatut {
  module: string;
  statut: string;
  jours: number;
  passages: number;
}

export interface Reouverture {
  libelle: string;
  rouverts: number;
  resolus: number;
  taux: number;
}

export interface DbsSynthese {
  dsi: number;
  dbs: number;
  dbs_ouverts: number;
  dbs_age_jours: number | null;
}

export interface ParetoItem {
  libelle: string;
  valeur: number;
  cumul_pct: number;
}

export interface Analyses {
  total: number;
  kpis: Kpis;
  par_module: AnalyseItem[];
  par_direction: AnalyseItem[];
  par_responsable: AnalyseItem[];
  par_priorite: AnalyseItem[];
  sla: { a_lheure: number; approche: number; depasse: number };
  sla_par_module: SlaModule[];
  sla_par_priorite: SlaPriorite[];
  matrice_risques: CaseRisque[];
  tendance: PointTendance[];
  activite: PointActivite[];
  durees_statuts: DureeStatut[];
  reouvertures: Reouverture[];
  vieillissement: AnalyseItem[];
  distribution_delais: AnalyseItem[];
  dbs: DbsSynthese;
  pareto_categories: ParetoItem[];
  pec_par_priorite: SlaPriorite[];
}

export interface GestionnaireEval {
  id: string;
  gestionnaire: string;
  volume: number;
  charge: number;
  resolus: number;
  mttr_jours: number | null;
  prise_en_charge_h: number | null;
  /** Respect SLA (%) : part des tickets résolus dans les temps. */
  respect_sla: number | null;
  /** Activités suivies comme contributeur : dans sa file, hors de son volume traité. */
  suivis: number;
}

export interface GestionnaireDetail extends GestionnaireEval {
  activite: PointActivite[];
}

export interface MoisEntete {
  cle: string;
  libelle: string;
}
export interface CelluleSla {
  mois: string;
  total: number;
  population_sla: number;
  sla_taux: number | null;
}
export interface LignePriorite {
  priorite: number;
  cible_minutes: number | null;
  cellules: CelluleSla[];
}
/** Volumétrie & SLA d'un module (incidents ou demandes), aux cibles SLA propres. */
export interface BlocVolumetrie {
  module: string;
  libelle: string;
  total_priorites: CelluleSla[];
  priorites: LignePriorite[];
}
export interface CelluleEntite {
  mois: string;
  total: number;
  fermes: number;
  ouverts: number;
  rejetes: number;
  incidents: number;
  demandes: number;
}
export interface LigneEntite {
  cle: string;
  libelle: string;
  total: number;
  fermes: number;
  ouverts: number;
  incidents: number;
  demandes: number;
  cellules: CelluleEntite[];
}
export type Granularite = 'heure' | 'jour' | 'semaine' | 'mois' | 'annee';

export interface CelluleNiveau {
  mois: string;
  total: number;
  fermes: number;
  ouverts: number;
  incidents: number;
  demandes: number;
}
export interface LigneNiveau {
  cle: string;
  libelle: string;
  niveau: string;
  total: number;
  fermes: number;
  ouverts: number;
  incidents: number;
  demandes: number;
  cellules: CelluleNiveau[];
}
export interface AnalysesMensuelles {
  granularite: Granularite;
  /** Fenêtre réellement agrégée (bornes des buckets), telle que le serveur l'a retenue. */
  debut: string;
  fin: string;
  mois: MoisEntete[];
  /** Un tableau volumétrie/SLA par module (incidents, demandes) : cibles SLA distinctes. */
  volumetrie: BlocVolumetrie[];
  entites: LigneEntite[];
  niveaux: LigneNiveau[];
}

/** Ajoute les modules retenus à une URL déjà formée. Liste vide = aucun filtre (tout est regardé),
 *  et le paramètre est répétable côté serveur : `?modules=incident&modules=demande`. */
function avecModules(base: string, modules: string[] = []): string {
  if (modules.length === 0) return base;
  const sep = base.includes('?') ? '&' : '?';
  return base + sep + modules.map((m) => `modules=${encodeURIComponent(m)}`).join('&');
}

export const analysesApi = {
  charger: (p: Periode, modules?: string[]): Promise<Analyses> =>
    api.get(avecModules(`/analyses${requetePeriode(p)}`, modules)),
  gestionnaires: (p: Periode, modules?: string[]): Promise<GestionnaireEval[]> =>
    api.get(avecModules(`/analyses/gestionnaires${requetePeriode(p)}`, modules)),
  gestionnaire: (id: string, p: Periode, modules?: string[]): Promise<GestionnaireDetail> =>
    api.get(avecModules(`/analyses/gestionnaire/${id}${requetePeriode(p)}`, modules)),
  mensuel: (p: Periode, statut: string | null = null): Promise<AnalysesMensuelles> => {
    const base = `/analyses/mensuel${requetePeriode(p)}`;
    const sep = base.includes('?') ? '&' : '?';
    return api.get(statut ? `${base}${sep}statut=${encodeURIComponent(statut)}` : base);
  },
};

/** Types partagés des tâches (projets, changements…). */

export type StatutTache = 'À faire' | 'En cours' | 'Terminée';
export const STATUTS_TACHE: StatutTache[] = ['À faire', 'En cours', 'Terminée'];

// Couleur = sens : à faire (neutre), en cours (vigilance/ambre), terminée (abouti/vert).
export const COULEUR_STATUT_TACHE: Record<StatutTache, string> = {
  'À faire': 'var(--text-muted)',
  'En cours': 'var(--status-warn)',
  'Terminée': 'var(--status-ok)',
};

export interface Chef {
  prenom: string;
  nom: string;
  email: string;
}

export interface Tache {
  id: string;
  titre: string;
  description: string | null;
  statut: StatutTache;
  assigne: Chef | null;
  assigne_id: string | null;
  echeance: string | null;
  ordre: number;
}

export interface NouvelleTache {
  titre: string;
  description?: string | null;
  assigne_id?: string | null;
  echeance?: string | null;
}

export type MajTache = Partial<{
  titre: string;
  description: string | null;
  statut: StatutTache;
  assigne_id: string | null;
  echeance: string | null;
}>;

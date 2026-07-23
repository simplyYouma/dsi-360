/** Types partagés des tâches (projets, changements…). */
import { Circle, CircleCheck, CircleDashed, type LucideIcon } from 'lucide-react';

export type StatutTache = 'À faire' | 'En cours' | 'Terminée';
export const STATUTS_TACHE: StatutTache[] = ['À faire', 'En cours', 'Terminée'];

// Couleur = sens : à faire (neutre), en cours (vigilance/ambre), terminée (abouti/vert).
export const COULEUR_STATUT_TACHE: Record<StatutTache, string> = {
  'À faire': 'var(--text-muted)',
  'En cours': 'var(--status-warn)',
  Terminée: 'var(--status-ok)',
};

// Forme = sens, avant même la couleur : cercle vide (rien n'est fait), cercle entamé (en
// chemin), coche (abouti). Se lit d'un coup d'œil, sans avoir à distinguer les teintes.
export const ICONE_STATUT_TACHE: Record<StatutTache, LucideIcon> = {
  'À faire': Circle,
  'En cours': CircleDashed,
  Terminée: CircleCheck,
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
  /** Date de fin d'une tâche terminée : porte le verdict d'échéance (à temps / en retard). */
  terminee_le?: string | null;
  ordre: number;
  nb_commentaires?: number;
  /** Messages de la tâche non encore lus par l'utilisateur connecté. */
  nb_non_vus?: number;
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

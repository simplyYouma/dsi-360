import { StatusBadge } from '@/design-system/primitives';

// Couleur = sens : on classe les statuts par signification métier.
const STATUT_OK = new Set([
  'Résolu',
  'Résolue',
  'Clôturé',
  'Clôturée',
  'Implémenté',
  'Validé',
  'Maîtrisé',
  'Accepté',
]);
const STATUT_DANGER = new Set(['Rejeté', 'Rejetée', 'Annulé', 'Retour arrière']);
// Vigilance : le sujet recule ou s'arrête (réouvert, suspendu, reporté).
const STATUT_WARN = new Set(['Réouvert', 'Réouverte', 'Suspendu', 'Reporté']);
// En attente d'une décision ou d'une revue (violet) : il avance, mais dépend d'un avis.
const STATUT_VALIDATION = new Set([
  'Soumis',
  'Évaluation',
  'CAB',
  'ECAB',
  'En validation',
  'En validation de clôture',
  'Revue post-implémentation',
  'Revue',
]);
// Vient d'arriver, personne n'y a touché (cyan). Distinct de « en cours » : c'est ce que
// « toujours la même couleur » désignait — un nouveau ne se voyait pas d'un actif.
const STATUT_NOUVEAU = new Set([
  'Nouveau',
  'Nouvelle',
  'Brouillon',
  'Identifié',
  'À engager',
  'Cadrage',
  'Ouverte',
  'À qualifier',
]);

/** Badge de statut coloré selon le sens (vert = abouti, rouge = négatif, ambre = vigilance,
 * indigo = en cours / nouveau). */
export function BadgeStatut({ statut }: { statut: string }): JSX.Element {
  if (STATUT_OK.has(statut)) return <StatusBadge statut="ok">{statut}</StatusBadge>;
  if (STATUT_DANGER.has(statut)) return <StatusBadge statut="danger">{statut}</StatusBadge>;
  if (STATUT_WARN.has(statut)) return <StatusBadge statut="warn">{statut}</StatusBadge>;
  if (STATUT_VALIDATION.has(statut))
    return <StatusBadge couleur="var(--cat-5)">{statut}</StatusBadge>;
  if (STATUT_NOUVEAU.has(statut)) return <StatusBadge couleur="var(--cat-7)">{statut}</StatusBadge>;
  // Le reste : en cours / actif (indigo).
  return <StatusBadge couleur="var(--cat-1)">{statut}</StatusBadge>;
}

const PRIORITE_COULEUR: Record<number, string> = {
  1: 'var(--status-danger)',
  2: 'var(--cat-3)',
  3: 'var(--cat-7)',
  4: 'var(--cat-1)',
  5: 'var(--text-muted)',
};

export function couleurStatut(statut: string): string {
  if (STATUT_OK.has(statut)) return 'var(--status-ok)';
  if (STATUT_DANGER.has(statut)) return 'var(--status-danger)';
  if (STATUT_WARN.has(statut)) return 'var(--status-warn)';
  if (STATUT_VALIDATION.has(statut)) return 'var(--cat-5)';
  if (STATUT_NOUVEAU.has(statut)) return 'var(--cat-7)';
  return 'var(--cat-1)';
}

export function BadgePriorite({ priorite }: { priorite: number }): JSX.Element {
  return (
    <StatusBadge couleur={PRIORITE_COULEUR[priorite] ?? 'var(--text-muted)'}>
      P{priorite}
    </StatusBadge>
  );
}

type EtatSla = 'a_lheure' | 'approche' | 'depasse';
const SLA: Record<EtatSla, { libelle: string; statut: 'ok' | 'warn' | 'danger' }> = {
  a_lheure: { libelle: "À l'heure", statut: 'ok' },
  approche: { libelle: 'Approche', statut: 'warn' },
  depasse: { libelle: 'Dépassé', statut: 'danger' },
};

export function BadgeSla({ etat }: { etat: EtatSla }): JSX.Element {
  return <StatusBadge statut={SLA[etat].statut}>{SLA[etat].libelle}</StatusBadge>;
}

const CRITICITE_MOT = ['', 'Très faible', 'Faible', 'Moyenne', 'Élevée', 'Critique'];

/** Criticité d'un risque (1..5) : vert (faible) → ambre (moyenne) → rouge (élevée/critique). */
export function BadgeCriticite({ niveau }: { niveau: number }): JSX.Element {
  const statut = niveau >= 4 ? 'danger' : niveau === 3 ? 'warn' : 'ok';
  return <StatusBadge statut={statut}>{CRITICITE_MOT[niveau] ?? `Niveau ${niveau}`}</StatusBadge>;
}

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

// Renommage d'affichage : le sigle ITIL reste le statut stocké (base, historique, workflow),
// mais on montre à l'écran un libellé clair. Un seul point de vérité, réutilisé partout.
const LIBELLE_STATUT: Record<string, string> = {
  CAB: 'Attente comité',
  ECAB: 'Validation express',
};

/** Libellé lisible d'un statut (renomme les sigles ; identité sinon). */
export function libelleStatut(statut: string): string {
  return LIBELLE_STATUT[statut] ?? statut;
}

// États qui closent ou annulent une activité : la transition vers eux demande une confirmation.
const STATUT_CLOTURANT = new Set([
  'Clôturé',
  'Clôturée',
  'Rejeté',
  'Rejetée',
  'Annulé',
  'Retour arrière',
  'Réalisé',
]);

/** La transition vers cet état clôture ou annule l'activité ? (confirmation exigée avant le clic). */
export function estTransitionCloturante(statut: string): boolean {
  return STATUT_CLOTURANT.has(statut);
}

/** Badge de statut coloré selon le sens (vert = abouti, rouge = négatif, ambre = vigilance,
 * indigo = en cours / nouveau). */
export function BadgeStatut({ statut }: { statut: string }): JSX.Element {
  const t = libelleStatut(statut);
  if (STATUT_OK.has(statut)) return <StatusBadge statut="ok">{t}</StatusBadge>;
  if (STATUT_DANGER.has(statut)) return <StatusBadge statut="danger">{t}</StatusBadge>;
  if (STATUT_WARN.has(statut)) return <StatusBadge statut="warn">{t}</StatusBadge>;
  if (STATUT_VALIDATION.has(statut)) return <StatusBadge couleur="var(--cat-5)">{t}</StatusBadge>;
  if (STATUT_NOUVEAU.has(statut)) return <StatusBadge couleur="var(--cat-7)">{t}</StatusBadge>;
  // Le reste : en cours / actif (indigo).
  return <StatusBadge couleur="var(--cat-1)">{t}</StatusBadge>;
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

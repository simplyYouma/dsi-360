import { StatusBadge } from '@/design-system/primitives';
import type { EtatSla } from '@/common/SablierSla';
import {
  libelleStatut as libelleDuCycle,
  tonStatut,
  verrouilleLeDossier,
  type Ton,
} from '@/common/cyclesDeVie';

// La couleur porte le sens, et le sens vient du domaine : chaque statut déclare son ton dans
// `domain/etats` côté serveur. Ici, on ne fait plus que traduire ce ton en couleur. Tant que
// l'écran tenait ses propres listes de statuts, elles divergeaient de celles du backend.
const COULEUR_TON: Record<Ton, string> = {
  nouveau: 'var(--cat-7)', // vient d'arriver, personne n'y a touché
  actif: 'var(--cat-1)', // du travail en cours chez nous
  attente: 'var(--cat-5)', // suspendu à la décision ou à l'avis d'un tiers
  recul: 'var(--status-warn)', // le dossier revient en arrière ou s'arrête
  succes: 'var(--status-ok)', // abouti
  echec: 'var(--status-danger)', // n'aboutira pas
};

/** Libellé lisible d'un statut (« CAB » → « Attente comité »). Identité si inconnu. */
export function libelleStatut(statut: string, module?: string): string {
  return libelleDuCycle(statut, module);
}

/** Passer à cet état verrouille-t-il le dossier ? (confirmation exigée avant le clic).
 *
 * C'est bien le verrou — l'état sans suite — et non la phase : « Résolu » ne réclame plus de
 * travail mais reste clôturable et réouvrable, il n'y a donc rien à confirmer.
 */
export function estTransitionCloturante(statut: string, module?: string): boolean {
  return verrouilleLeDossier(statut, module);
}

/** Badge de statut, coloré selon le ton déclaré par le domaine. */
export function BadgeStatut({ statut, module }: { statut: string; module?: string }): JSX.Element {
  return (
    <StatusBadge couleur={COULEUR_TON[tonStatut(statut, module)]}>
      {libelleStatut(statut, module)}
    </StatusBadge>
  );
}

const PRIORITE_COULEUR: Record<number, string> = {
  1: 'var(--status-danger)',
  2: 'var(--cat-3)',
  3: 'var(--cat-7)',
  4: 'var(--cat-1)',
  5: 'var(--text-muted)',
};

export function couleurStatut(statut: string, module?: string): string {
  return COULEUR_TON[tonStatut(statut, module)];
}

export function BadgePriorite({ priorite }: { priorite: number }): JSX.Element {
  return (
    <StatusBadge couleur={PRIORITE_COULEUR[priorite] ?? 'var(--text-muted)'}>
      P{priorite}
    </StatusBadge>
  );
}

const SLA: Record<EtatSla, { libelle: string; statut: 'ok' | 'warn' | 'danger' | 'neutre' }> = {
  a_lheure: { libelle: "À l'heure", statut: 'ok' },
  approche: { libelle: 'Approche', statut: 'warn' },
  depasse: { libelle: 'Dépassé', statut: 'danger' },
  // Le dossier est clos : le délai ne court plus, il n'y a plus de verdict à rendre.
  termine: { libelle: 'Terminé', statut: 'neutre' },
};

export function BadgeSla({ etat }: { etat: EtatSla }): JSX.Element {
  const { libelle, statut } = SLA[etat];
  if (statut === 'neutre') {
    return <StatusBadge couleur="var(--text-muted)">{libelle}</StatusBadge>;
  }
  return <StatusBadge statut={statut}>{libelle}</StatusBadge>;
}

const CRITICITE_MOT = ['', 'Très faible', 'Faible', 'Moyenne', 'Élevée', 'Critique'];

/** Criticité d'un risque (1..5) : vert (faible) → ambre (moyenne) → rouge (élevée/critique). */
export function BadgeCriticite({ niveau }: { niveau: number }): JSX.Element {
  const statut = niveau >= 4 ? 'danger' : niveau === 3 ? 'warn' : 'ok';
  return <StatusBadge statut={statut}>{CRITICITE_MOT[niveau] ?? `Niveau ${niveau}`}</StatusBadge>;
}

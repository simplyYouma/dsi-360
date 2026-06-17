import type { ReactNode } from 'react';
import { cx } from '@/common/cx';
import styles from './StatusBadge.module.css';

type Statut = 'ok' | 'warn' | 'danger' | 'neutre';

interface StatusBadgeProps {
  children: ReactNode;
  /** Statut sémantique (couleur = sens). */
  statut?: Statut;
  /** Couleur catégorielle (ex. "var(--cat-1)") — touche de couleur sans valeur de statut. */
  couleur?: string;
}

/** Étiquette de statut/catégorie. Tons sémantiques OU palette catégorielle (var(--cat-n)). */
export function StatusBadge({ children, statut = 'neutre', couleur }: StatusBadgeProps): JSX.Element {
  const styleCategoriel =
    couleur !== undefined
      ? {
          color: couleur,
          background: `color-mix(in srgb, ${couleur} 14%, transparent)`,
        }
      : undefined;
  return (
    <span
      className={cx(styles.badge, couleur === undefined && styles[statut])}
      style={styleCategoriel}
    >
      {children}
    </span>
  );
}

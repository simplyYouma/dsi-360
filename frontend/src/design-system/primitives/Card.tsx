import type { HTMLAttributes, ReactNode } from 'react';
import { cx } from '@/common/cx';
import styles from './Card.module.css';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  /** Retire le padding interne (pour les cartes qui contiennent un tableau pleine largeur). */
  sansPadding?: boolean;
}

/** Surface premium : fond, rayon, bordure légère, ombre douce. */
export function Card({ children, sansPadding = false, className, ...rest }: CardProps): JSX.Element {
  return (
    <div className={cx(styles.card, sansPadding && styles.sansPadding, className)} {...rest}>
      {children}
    </div>
  );
}

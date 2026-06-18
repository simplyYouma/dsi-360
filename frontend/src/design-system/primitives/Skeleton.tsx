import { cx } from '@/common/cx';
import styles from './Skeleton.module.css';

interface SkeletonProps {
  largeur?: string;
  hauteur?: string;
  radius?: string;
  className?: string | undefined;
}

/** Bloc de chargement à reflet doux (placeholder). */
export function Skeleton({
  largeur = '100%',
  hauteur = '14px',
  radius = 'var(--radius-sm)',
  className,
}: SkeletonProps): JSX.Element {
  return (
    <span
      className={cx(styles.skeleton, className)}
      style={{ width: largeur, height: hauteur, borderRadius: radius }}
      aria-hidden="true"
    />
  );
}

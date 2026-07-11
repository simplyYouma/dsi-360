import { cx } from './cx';
import styles from './BarreAvancement.module.css';

interface Props {
  /** Avancement 0..100. */
  valeur: number;
  /** Variante compacte (liste) : barre plus fine, valeur à côté. */
  compact?: boolean;
}

/**
 * Barre d'avancement d'un projet : dégradé animé, verte à 100 %. Une seule règle visuelle,
 * partagée entre la fiche et la liste, pour qu'elles se ressemblent.
 */
export function BarreAvancement({ valeur, compact = false }: Props): JSX.Element {
  const v = Math.max(0, Math.min(100, valeur));
  return (
    <div className={cx(styles.bloc, compact && styles.compact)}>
      <div className={styles.rail}>
        <div
          className={cx(styles.remplissage, v === 100 && styles.complet)}
          style={{ width: `${v}%` }}
        />
      </div>
      <span className={styles.valeur}>{v}%</span>
    </div>
  );
}

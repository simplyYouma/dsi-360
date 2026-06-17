import { ChevronRight } from 'lucide-react';
import type { ReactNode } from 'react';
import { cx } from '@/common/cx';
import styles from './LigneListe.module.css';

interface LigneListeProps {
  /** Pastille de gauche : initiales, icône, ou avatar. */
  pastille: ReactNode;
  libelle: string;
  /** Couleur de fond de la pastille (défaut : neutre). */
  fondPastille?: string;
  onClick?: () => void;
  /** Masque le chevron de droite (ligne non navigable). */
  sansChevron?: boolean;
}

/** Ligne de liste cliquable (pattern des modales de sélection). */
export function LigneListe({
  pastille,
  libelle,
  fondPastille,
  onClick,
  sansChevron = false,
}: LigneListeProps): JSX.Element {
  return (
    <button type="button" className={cx(styles.ligne)} onClick={onClick}>
      <span
        className={styles.pastille}
        style={fondPastille !== undefined ? { background: fondPastille } : undefined}
      >
        {pastille}
      </span>
      <span className={styles.libelle}>{libelle}</span>
      {!sansChevron && <ChevronRight size={20} className={styles.chevron} aria-hidden="true" />}
    </button>
  );
}

import { IndicateurDiscussion } from './IndicateurDiscussion';
import styles from './CelluleReference.module.css';

interface Props {
  reference: string;
  nombre: number;
  nonVus?: number;
}

/** Première cellule d'une ligne d'activité : la marque de discussion épinglée à gauche, puis la
 *  référence. La marque passe en couleur avec le compteur de non-lus (comme sur les réseaux). */
export function CelluleReference({ reference, nombre, nonVus = 0 }: Props): JSX.Element {
  return (
    <span className={styles.cellule}>
      <span className={styles.marque}>
        <IndicateurDiscussion nombre={nombre} nonVus={nonVus} />
      </span>
      <span className={styles.reference}>{reference}</span>
    </span>
  );
}

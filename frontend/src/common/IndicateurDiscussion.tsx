import { MessageSquareText } from 'lucide-react';
import { cx } from './cx';
import styles from './IndicateurDiscussion.module.css';

interface Props {
  /** Nombre total de messages du fil. */
  nombre: number;
  /** Messages non lus par l'utilisateur connecté (mis en couleur, comme sur les réseaux). */
  nonVus?: number;
}

/** Marque de discussion épinglée en tête de ligne : discrète si tout est lu, colorée
 *  avec le compteur de nouveaux messages non lus par l'utilisateur connecté sinon. */
export function IndicateurDiscussion({ nombre, nonVus = 0 }: Props): JSX.Element | null {
  if (nombre <= 0) return null;
  const aDuNouveau = nonVus > 0;
  return (
    <span
      className={cx(styles.marque, aDuNouveau && styles.nouveau)}
      title={
        aDuNouveau
          ? `${nonVus} nouveau${nonVus > 1 ? 'x' : ''} message${nonVus > 1 ? 's' : ''} non lu${nonVus > 1 ? 's' : ''}`
          : `${nombre} message${nombre > 1 ? 's' : ''}`
      }
    >
      <MessageSquareText size={14} />
      <span className={styles.nb}>{aDuNouveau ? nonVus : nombre}</span>
    </span>
  );
}

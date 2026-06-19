import { MessageSquareText } from 'lucide-react';
import styles from './IndicateurDiscussion.module.css';

/** Marque discrète en bout de ligne quand une discussion (commentaire) existe. */
export function IndicateurDiscussion({ nombre }: { nombre: number }): JSX.Element | null {
  if (nombre <= 0) return null;
  return (
    <span className={styles.marque} title={`${nombre} commentaire${nombre > 1 ? 's' : ''}`}>
      <MessageSquareText size={14} />
      <span className={styles.nb}>{nombre}</span>
    </span>
  );
}

import styles from './PastilleEcheance.module.css';

interface Props {
  /** Date d'échéance (ISO ou null). */
  date: string | null | undefined;
  /** Mot de tête : « Échéance », « Revue »… */
  prefixe?: string;
  /** Nombre de jours en deçà duquel on alerte (défaut 7). Au-delà, discret. */
  seuil?: number;
}

/**
 * Compteur d'échéance : rouge si dépassé, ambre si l'échéance approche, discret sinon.
 * Une seule règle pour toute l'application — projet, revue périodique, etc.
 */
export function PastilleEcheance({
  date,
  prefixe = 'Échéance',
  seuil = 7,
}: Props): JSX.Element | null {
  if (date === null || date === undefined || date === '') return null;
  const jours = Math.ceil((new Date(date).setHours(23, 59, 59, 999) - Date.now()) / 86_400_000);
  if (jours < 0) {
    return (
      <span className={styles.retard}>
        {prefixe} dépassée · {Math.abs(jours)} j
      </span>
    );
  }
  if (jours <= seuil) {
    return (
      <span className={styles.proche}>
        {jours === 0 ? `${prefixe} aujourd’hui` : `${prefixe} dans ${jours} j`}
      </span>
    );
  }
  return (
    <span className={styles.calme}>
      {prefixe} dans {jours} j
    </span>
  );
}

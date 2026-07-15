import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useRafraichissement } from '@/common/useRafraichissement';
import styles from './BandeauStats.module.css';

interface Stats {
  total: number;
  en_cours: number;
  termines: number;
  en_retard: number;
}

interface Props {
  /** Base du module (ex. `/incidents`) : les stats sont lues sur `${base}/stats`. */
  base: string;
  /** Signal de rafraîchissement : quand il change, les compteurs se relisent (ex. `total` courant). */
  signal?: number;
}

/**
 * En-tête de liste : compteurs par état (total, en cours, terminés, en retard) du périmètre.
 * La couleur n'est portée que par « En retard », et seulement s'il y en a — le sens, pas la déco.
 */
export function BandeauStats({ base, signal }: Props): JSX.Element | null {
  const [stats, setStats] = useState<Stats | null>(null);

  const charger = useCallback((): void => {
    void api
      .get<Stats>(`${base}/stats`)
      .then(setStats)
      .catch(() => undefined);
  }, [base]);

  useEffect(() => {
    charger();
  }, [charger, signal]);
  useRafraichissement(charger);

  if (stats === null) return null;
  const retard = stats.en_retard > 0;
  return (
    <div className={styles.bandeau} role="group" aria-label="État de la liste">
      <span className={styles.stat}>
        <b className={styles.valeur}>{stats.total}</b>
        <span className={styles.libelle}>Total</span>
      </span>
      <span className={styles.stat}>
        <b className={styles.valeur}>{stats.en_cours}</b>
        <span className={styles.libelle}>En cours</span>
      </span>
      <span className={styles.stat}>
        <b className={styles.valeur}>{stats.termines}</b>
        <span className={styles.libelle}>Terminés</span>
      </span>
      <span className={retard ? styles.statRetard : styles.stat}>
        <b className={styles.valeur}>{stats.en_retard}</b>
        <span className={styles.libelle}>En retard</span>
      </span>
    </div>
  );
}

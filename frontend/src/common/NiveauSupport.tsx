import styles from './NiveauSupport.module.css';

interface Props {
  niveau: number;
  transfereDbs: boolean;
  /** Ligne de tableau : rendu compact, sans phrase explicative. */
  compact?: boolean;
}

/** Où se trouve un ticket importé — **déduit**, jamais décidé ici.
 *
 *  Le gestionnaire vient du fichier quotidien. S'il est l'un des nôtres, le ticket est à son
 *  niveau (N1 ou N2). Sinon c'est DBS, et le ticket est au niveau 3. Le support le voit bouger
 *  seul après chaque import. */
export function NiveauSupport({ niveau, transfereDbs, compact = false }: Props): JSX.Element {
  const libelle = transfereDbs ? 'DBS' : `N${niveau}`;
  const titre = transfereDbs
    ? 'Traité par DBS, hors de la plateforme (niveau 3)'
    : `Support de niveau ${niveau} à la DSI`;

  return (
    <span className={styles.bloc}>
      <span className={transfereDbs ? styles.dbs : styles.niveau} title={titre}>
        {libelle}
      </span>
      {!compact && (
        <span className={styles.note}>
          {transfereDbs
            ? 'Traité par DBS — le niveau suit le gestionnaire du rapport importé.'
            : 'Déduit du gestionnaire, à chaque import.'}
        </span>
      )}
    </span>
  );
}

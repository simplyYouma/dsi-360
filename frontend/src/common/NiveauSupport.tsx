import styles from './NiveauSupport.module.css';

interface Props {
  /** `null` : aucun gestionnaire renseigné à l'import — le niveau est inconnu. */
  niveau: number | null;
  transfereDbs: boolean;
  /** Ligne de tableau : rendu compact, sans phrase explicative. */
  compact?: boolean;
}

/** Où se trouve un ticket importé — **déduit**, jamais décidé ici.
 *
 *  Le gestionnaire vient du fichier quotidien. S'il est l'un des nôtres, le ticket est à son
 *  niveau (N1 ou N2). S'il porte un autre nom, c'est DBS (niveau 3). Sans gestionnaire renseigné,
 *  le ticket n'est chez personne : on ne l'attribue pas à DBS. Le support le voit bouger seul
 *  après chaque import. */
export function NiveauSupport({ niveau, transfereDbs, compact = false }: Props): JSX.Element {
  const inconnu = !transfereDbs && niveau === null;
  const libelle = inconnu ? '—' : transfereDbs ? 'DBS' : `N${niveau}`;
  const titre = inconnu
    ? 'Aucun gestionnaire renseigné dans le rapport importé : niveau inconnu.'
    : transfereDbs
      ? 'Traité par DBS, hors de la plateforme (niveau 3)'
      : `Support de niveau ${niveau} à la DSI`;

  return (
    <span className={styles.bloc}>
      <span
        className={inconnu ? styles.inconnu : transfereDbs ? styles.dbs : styles.niveau}
        title={titre}
      >
        {libelle}
      </span>
      {!compact && (
        <span className={styles.note}>
          {inconnu
            ? 'Gestionnaire non renseigné dans le rapport importé.'
            : transfereDbs
              ? 'Traité par DBS — le niveau suit le gestionnaire du rapport importé.'
              : 'Déduit du gestionnaire, à chaque import.'}
        </span>
      )}
    </span>
  );
}

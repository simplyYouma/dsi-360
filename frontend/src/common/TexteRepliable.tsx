import { useLayoutEffect, useRef, useState } from 'react';
import { cx } from './cx';
import styles from './TexteRepliable.module.css';

interface Props {
  texte: string;
  /** Nombre de lignes visibles avant repli (défaut 4). */
  lignes?: number;
  /** Classe du texte (reprend l'apparence du champ qui l'accueille). */
  classe?: string | undefined;
  /** Clic sur le texte — ex. passer en édition. Absent : le texte n'est pas cliquable. */
  onTexte?: (() => void) | undefined;
  /** Infobulle du texte (ex. raison d'un champ figé). */
  titre?: string | undefined;
  'aria-label'?: string | undefined;
}

/** Texte long replié sur quelques lignes, dépliable au clic.
 *
 *  Une description de dix lignes repoussait tout le reste de la fiche hors de l'écran : le cycle
 *  de vie, les échéances, l'historique. On la replie donc, et l'on rend le reste visible d'emblée.
 *
 *  L'invite « Voir plus » n'apparaît **que si du texte est réellement caché** : on la mesure après
 *  rendu (hauteur réelle contre hauteur visible) plutôt que de compter les caractères, qui ne
 *  disent rien de la largeur disponible ni des retours à la ligne.
 */
export function TexteRepliable({
  texte,
  lignes = 4,
  classe,
  onTexte,
  titre,
  'aria-label': ariaLabel,
}: Props): JSX.Element {
  const ref = useRef<HTMLSpanElement>(null);
  const [deborde, setDeborde] = useState(false);
  const [deplie, setDeplie] = useState(false);

  useLayoutEffect(() => {
    // Une fois déplié, le texte ne déborde plus par construction : on cesse de mesurer, sinon
    // l'invite « Réduire » disparaîtrait aussitôt affichée.
    if (deplie) return;
    const noeud = ref.current;
    if (noeud === null) return;
    // Marge d'un pixel : les hauteurs fractionnaires font mentir une comparaison stricte.
    setDeborde(noeud.scrollHeight - noeud.clientHeight > 1);
  }, [texte, lignes, deplie]);

  const contenu = (
    <span
      ref={ref}
      className={deplie ? undefined : styles.replie}
      style={{ '--lignes': lignes } as React.CSSProperties}
    >
      {texte}
    </span>
  );

  return (
    <div className={styles.bloc}>
      {onTexte !== undefined ? (
        <button
          type="button"
          className={cx(styles.texte, classe)}
          onClick={onTexte}
          title={titre}
          aria-label={ariaLabel}
        >
          {contenu}
        </button>
      ) : (
        <p className={cx(styles.texte, classe)} title={titre}>
          {contenu}
        </p>
      )}
      {deborde && (
        <button
          type="button"
          className={styles.plus}
          onClick={() => setDeplie((v) => !v)}
          aria-expanded={deplie}
        >
          {deplie ? 'Réduire' : 'Voir plus'}
        </button>
      )}
    </div>
  );
}

import { useEffect, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { cx } from './cx';
import styles from './ChampInline.module.css';

interface Props {
  valeur: string;
  onValider: (v: string) => void;
  placeholder?: string;
  multiligne?: boolean;
  inputMode?: 'numeric';
  /** Mode création : champ toujours en édition (pas de clic requis). */
  toujoursEdition?: boolean;
  /** Classe appliquée au texte affiché (ex. style d'un titre). */
  classeTexte?: string | undefined;
  'aria-label'?: string | undefined;
}

/** Champ éditable au clic : affiche la valeur ; clic → saisie ; Entrée/blur → validation. */
export function ChampInline({
  valeur,
  onValider,
  placeholder,
  multiligne = false,
  inputMode,
  toujoursEdition = false,
  classeTexte,
  'aria-label': ariaLabel,
}: Props): JSX.Element {
  const [edite, setEdite] = useState(false);
  const [brouillon, setBrouillon] = useState(valeur);
  useEffect(() => setBrouillon(valeur), [valeur]);

  const enEdition = edite || toujoursEdition;

  const valider = (): void => {
    if (!toujoursEdition) setEdite(false);
    if (brouillon !== valeur) onValider(brouillon);
  };
  const annuler = (): void => {
    setBrouillon(valeur);
    if (!toujoursEdition) setEdite(false);
  };

  if (!enEdition) {
    return (
      <button
        type="button"
        className={cx(styles.affichage, classeTexte)}
        onClick={() => setEdite(true)}
        aria-label={ariaLabel}
      >
        {valeur !== '' ? valeur : <span className={styles.placeholder}>{placeholder ?? '—'}</span>}
      </button>
    );
  }

  const surTouche = (e: ReactKeyboardEvent<HTMLInputElement | HTMLTextAreaElement>): void => {
    if (e.key === 'Escape') annuler();
    if (e.key === 'Enter' && !multiligne) e.currentTarget.blur();
  };

  return multiligne ? (
    <textarea
      className={styles.input}
      rows={3}
      value={brouillon}
      placeholder={placeholder}
      autoFocus={!toujoursEdition}
      aria-label={ariaLabel}
      onChange={(e) => setBrouillon(e.target.value)}
      onBlur={valider}
      onKeyDown={surTouche}
    />
  ) : (
    <input
      className={styles.input}
      value={brouillon}
      placeholder={placeholder}
      inputMode={inputMode}
      autoFocus={!toujoursEdition}
      aria-label={ariaLabel}
      onChange={(e) =>
        setBrouillon(inputMode === 'numeric' ? e.target.value.replace(/[^0-9]/g, '') : e.target.value)
      }
      onBlur={valider}
      onKeyDown={surTouche}
    />
  );
}

import { useEffect, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { cx } from './cx';
import { TexteRepliable } from './TexteRepliable';
import styles from './ChampInline.module.css';

interface Props {
  valeur: string;
  onValider: (v: string) => void;
  /** Marqueur affiché quand le champ est vide, hors saisie (défaut « — »). */
  placeholder?: string;
  /** Indication affichée dans la zone de saisie tant qu'elle est vide (ex. « Décrivez… »). */
  indication?: string | undefined;
  multiligne?: boolean;
  inputMode?: 'numeric';
  /** Mode création : champ toujours en édition (pas de clic requis). */
  toujoursEdition?: boolean;
  /** Classe appliquée au texte (affiché ET en saisie), ex. style d'un titre. */
  classeTexte?: string | undefined;
  /** Variante « titre » : saisie discrète, sans encadré. */
  titre?: boolean;
  /** Sans droit d'écrire : la valeur s'affiche, le clic n'ouvre rien. */
  lectureSeule?: boolean;
  /** Pourquoi le champ ne s'édite pas (infobulle). */
  titreLectureSeule?: string | undefined;
  /** Replie l'affichage sur ce nombre de lignes, dépliable au clic (textes longs). N'affecte
   *  que la lecture : la saisie reste entière. */
  repliable?: number | undefined;
  'aria-label'?: string | undefined;
}

/** Champ éditable au clic : affiche la valeur ; clic → saisie ; Entrée/blur → validation. */
export function ChampInline({
  valeur,
  onValider,
  placeholder,
  indication,
  multiligne = false,
  inputMode,
  toujoursEdition = false,
  classeTexte,
  titre = false,
  lectureSeule = false,
  titreLectureSeule,
  repliable,
  'aria-label': ariaLabel,
}: Props): JSX.Element {
  const [edite, setEdite] = useState(false);
  const [brouillon, setBrouillon] = useState(valeur);
  useEffect(() => setBrouillon(valeur), [valeur]);

  const enEdition = !lectureSeule && (edite || toujoursEdition);

  const valider = (): void => {
    if (!toujoursEdition) setEdite(false);
    if (brouillon !== valeur) onValider(brouillon);
  };

  /** Saisie : le brouillon local suit toujours, le parent seulement en mode création.
   *
   *  En clic-pour-éditer, la valeur ne remonte qu'à la validation (Entrée / sortie du champ) :
   *  c'est ce qui permet d'annuler par Échap sans avoir rien écrit dans la fiche.
   *
   *  En mode création (`toujoursEdition`), c'est le parent qui tient le brouillon du formulaire,
   *  et souvent un bouton « Créer » qui s'active dessus. Attendre la sortie du champ le laissait
   *  désactivé au moment précis où l'on veut cliquer : on tapait le titre, on visait le bouton,
   *  et le clic tombait sur un bouton encore éteint. La frappe doit donc remonter aussitôt.
   */
  const saisir = (val: string): void => {
    setBrouillon(val);
    if (toujoursEdition) onValider(val);
  };
  const annuler = (): void => {
    setBrouillon(valeur);
    if (!toujoursEdition) setEdite(false);
  };

  if (!enEdition) {
    // Texte long : on le replie, et l'on garde le clic-pour-éditer sur le texte lui-même.
    // L'invite « Voir plus » vit à côté, jamais dedans : deux boutons imbriqués n'existent pas.
    if (repliable !== undefined && valeur !== '') {
      return (
        <TexteRepliable
          texte={valeur}
          lignes={repliable}
          classe={cx(styles.affichage, classeTexte, lectureSeule && styles.affichageFige)}
          onTexte={lectureSeule ? undefined : () => setEdite(true)}
          titre={lectureSeule ? titreLectureSeule : undefined}
          aria-label={ariaLabel}
        />
      );
    }
    return (
      <button
        type="button"
        className={cx(styles.affichage, classeTexte, lectureSeule && styles.affichageFige)}
        onClick={() => !lectureSeule && setEdite(true)}
        disabled={lectureSeule}
        title={lectureSeule ? titreLectureSeule : undefined}
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

  const classeInput = cx(styles.input, titre && styles.titre, classeTexte);

  return multiligne ? (
    <textarea
      className={classeInput}
      rows={3}
      value={brouillon}
      placeholder={indication ?? placeholder}
      autoFocus={!toujoursEdition}
      aria-label={ariaLabel}
      onChange={(e) => saisir(e.target.value)}
      onBlur={valider}
      onKeyDown={surTouche}
    />
  ) : (
    <input
      className={classeInput}
      value={brouillon}
      placeholder={indication ?? placeholder}
      inputMode={inputMode}
      autoFocus={!toujoursEdition}
      aria-label={ariaLabel}
      onChange={(e) =>
        saisir(inputMode === 'numeric' ? e.target.value.replace(/[^0-9]/g, '') : e.target.value)
      }
      onBlur={valider}
      onKeyDown={surTouche}
    />
  );
}

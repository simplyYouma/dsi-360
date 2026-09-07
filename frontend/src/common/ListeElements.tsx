import { useState, type KeyboardEvent } from 'react';
import { Plus, X, type LucideIcon } from 'lucide-react';
import styles from './ListeElements.module.css';

interface Props {
  valeur: string[];
  /** Non fournie : la liste se lit seulement. La permission vient du serveur. */
  onChange?: ((elements: string[]) => void) | undefined;
  /** Icône sémantique de la nature listée (risque, impact…) : une forme se lit plus vite qu'un
   *  point, et reste lisible pour qui distingue mal les couleurs. */
  icone: LucideIcon;
  /** Teinte de la nature listée. Réservée au sens, jamais décorative. */
  couleur: string;
  indication: string;
  /** Combien d'éléments restent visibles avant le fondu. Au-delà, la carte s'ouvre au clic. */
  apercu?: number;
  /** Pourquoi la liste ne s'édite pas (infobulle). */
  titreLectureSeule?: string | undefined;
}

const MINI = 3;

/**
 * Liste d'éléments courts saisis un par un — risques d'un sujet, impacts attendus.
 *
 * Trois partis pris :
 *
 * 1. **Un par un, à la touche Entrée.** Un sujet de COPIL porte rarement un seul risque : il en
 *    reçoit au fil des comités. Les écrire dans un pavé de texte obligeait à les séparer soi-même
 *    et rendait impossible d'en retirer un sans réécrire le reste.
 * 2. **On n'affiche pas tout.** Une fiche qui déroule six risques repousse le cycle de vie hors de
 *    l'écran. Les premiers se lisent, le reste s'estompe sous un fondu — et le compteur dit
 *    combien manquent, plutôt que de le cacher.
 * 3. **Le clic ouvre sur place.** La carte se déplie dans la fiche, sans empiler une modale
 *    par-dessus celle qu'on lit déjà.
 */
export function ListeElements({
  valeur,
  onChange,
  icone: Icone,
  couleur,
  indication,
  apercu = 2,
  titreLectureSeule,
}: Props): JSX.Element {
  const [saisie, setSaisie] = useState('');
  const [ouvert, setOuvert] = useState(false);
  const modifiable = onChange !== undefined;
  const caches = Math.max(0, valeur.length - apercu);
  // Déplié, ou trop court pour qu'il y ait quelque chose à cacher : on montre tout.
  const visibles = ouvert || caches === 0 ? valeur : valeur.slice(0, apercu);

  const ajouter = (): void => {
    const texte = saisie.trim();
    if (!modifiable || texte.length < MINI) return;
    // Le serveur écarte les doublons de son côté ; l'écran évite d'abord de les proposer.
    if (!valeur.includes(texte)) onChange([...valeur, texte]);
    setSaisie('');
  };

  const touche = (e: KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'Enter') {
      e.preventDefault();
      ajouter();
    }
  };

  if (valeur.length === 0 && !modifiable) {
    return (
      <span className={styles.vide} title={titreLectureSeule}>
        —
      </span>
    );
  }

  return (
    <div className={styles.bloc}>
      {valeur.length > 0 && (
        <div className={ouvert || caches === 0 ? styles.listeOuverte : styles.listeRepliee}>
          <ul className={styles.liste}>
            {visibles.map((el, i) => (
              <li key={`${el}-${i}`} className={styles.element}>
                <Icone size={14} className={styles.icone} style={{ color: couleur }} />
                <span className={styles.texte}>{el}</span>
                {modifiable && (
                  <button
                    type="button"
                    className={styles.retirer}
                    onClick={() => onChange(valeur.filter((_, j) => j !== i))}
                    aria-label={`Retirer « ${el} »`}
                    title="Retirer"
                  >
                    <X size={12} />
                  </button>
                )}
              </li>
            ))}
          </ul>
          {/* Le fondu ne cache pas : il annonce qu'il y a une suite, et le bouton la donne. */}
          {caches > 0 && !ouvert && <span className={styles.fondu} aria-hidden="true" />}
        </div>
      )}

      {caches > 0 && (
        <button
          type="button"
          className={styles.deplier}
          onClick={() => setOuvert(!ouvert)}
          aria-expanded={ouvert}
        >
          {ouvert ? 'Replier' : `Voir les ${valeur.length} éléments`}
        </button>
      )}

      {modifiable && (
        <div className={styles.ajout}>
          <input
            className={styles.champ}
            value={saisie}
            onChange={(e) => setSaisie(e.target.value)}
            onKeyDown={touche}
            placeholder={indication}
            aria-label={indication}
          />
          <button
            type="button"
            className={styles.bouton}
            onClick={ajouter}
            disabled={saisie.trim().length < MINI}
            title="Ajouter (Entrée)"
            aria-label="Ajouter"
          >
            <Plus size={15} />
          </button>
        </div>
      )}
    </div>
  );
}

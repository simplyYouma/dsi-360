import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { Plus, X, type LucideIcon } from 'lucide-react';
import { ChampInline } from './ChampInline';
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
  /** Pourquoi la liste ne s'édite pas (infobulle). */
  titreLectureSeule?: string | undefined;
}

const MINI = 3;

/**
 * Liste d'éléments courts saisis un par un — risques d'un sujet, impacts attendus.
 *
 * Quatre partis pris :
 *
 * 1. **Un par un, à la touche Entrée.** Un sujet de COPIL porte rarement un seul risque : il en
 *    reçoit au fil des comités. Les écrire dans un pavé de texte obligeait à les séparer soi-même
 *    et rendait impossible d'en retirer un sans réécrire le reste.
 * 2. **Chaque élément se corrige sur place.** Ajouter et retirer ne suffisent pas : une formulation
 *    se précise d'un comité à l'autre, et devoir supprimer puis retaper pour changer un mot faisait
 *    perdre le texte. Le clic ouvre la saisie — le même `ChampInline` que partout ailleurs.
 * 3. **On n'affiche pas tout.** Une fiche qui déroule six risques repousse le cycle de vie hors de
 *    l'écran. Ce qui dépasse s'estompe, et le compteur dit combien il y en a.
 * 4. **Le débordement se mesure, il ne se déduit pas d'un nombre d'éléments.** La place disponible
 *    varie — la colonne s'étire sur la hauteur de sa voisine — et un seul risque long déborde autant
 *    que trois courts. Compter les éléments coupait une phrase en plein milieu alors que la place
 *    restait, et laissait les deux colonnes se terminer à des hauteurs différentes.
 */
export function ListeElements({
  valeur,
  onChange,
  icone: Icone,
  couleur,
  indication,
  titreLectureSeule,
}: Props): JSX.Element {
  const [saisie, setSaisie] = useState('');
  const [ouvert, setOuvert] = useState(false);
  const [deborde, setDeborde] = useState(false);
  const zone = useRef<HTMLDivElement>(null);
  const modifiable = onChange !== undefined;

  useEffect(() => {
    const el = zone.current;
    if (el === null) return undefined;
    const mesurer = (): void => setDeborde(el.scrollHeight - el.clientHeight > 2);
    mesurer();
    const observateur = new ResizeObserver(mesurer);
    observateur.observe(el);
    return () => observateur.disconnect();
  }, [valeur, ouvert]);

  const ajouter = (): void => {
    const texte = saisie.trim();
    if (!modifiable || texte.length < MINI) return;
    // Le serveur écarte les doublons de son côté ; l'écran évite d'abord de les proposer.
    if (!valeur.includes(texte)) onChange([...valeur, texte]);
    setSaisie('');
  };

  /** Correction d'un élément. Vidé, il n'est pas effacé : on retire par la croix, jamais par
   *  accident en sélectionnant tout puis en sortant du champ. */
  const remplacer = (index: number, texte: string): void => {
    const propre = texte.trim();
    if (!modifiable || propre.length < MINI || propre === valeur[index]) return;
    if (valeur.some((el, j) => j !== index && el === propre)) return;
    onChange(valeur.map((el, j) => (j === index ? propre : el)));
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

  // Déplié, la bascule reste offerte même si tout tient désormais : sans elle, on ne saurait plus
  // refermer ce que l'on vient d'ouvrir.
  const bascule = ouvert || deborde;

  return (
    <div className={styles.bloc}>
      {valeur.length > 0 && (
        <div ref={zone} className={ouvert ? styles.listeOuverte : styles.listeRepliee}>
          <ul className={styles.liste}>
            {valeur.map((el, i) => (
              <li key={`${el}-${i}`} className={styles.element}>
                <Icone size={14} className={styles.icone} style={{ color: couleur }} />
                <div className={styles.texte}>
                  <ChampInline
                    valeur={el}
                    multiligne
                    onValider={(t) => remplacer(i, t)}
                    lectureSeule={!modifiable}
                    titreLectureSeule={titreLectureSeule}
                    aria-label={`Modifier « ${el} »`}
                  />
                </div>
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
        </div>
      )}

      {bascule && (
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

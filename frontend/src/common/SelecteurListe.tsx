import { useEffect, useRef, useState } from 'react';
import { ChevronDown, Check } from 'lucide-react';
import { cx } from './cx';
import styles from './SelecteurListe.module.css';

export interface OptionListe {
  valeur: string;
  libelle: string;
}

interface Props {
  options: OptionListe[];
  valeur: string | null;
  onChange: (v: string | null) => void;
  placeholder?: string;
  permettreVide?: boolean;
  libelleVide?: string;
}

/** Liste déroulante maison (popover) — aucun composant natif navigateur. */
interface Position {
  top: number;
  left: number;
  width: number;
}

export function SelecteurListe({
  options,
  valeur,
  onChange,
  placeholder = 'Sélectionner…',
  permettreVide = false,
  libelleVide = 'Aucune',
}: Props): JSX.Element {
  const [ouvert, setOuvert] = useState(false);
  const [pos, setPos] = useState<Position | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const declencheur = useRef<HTMLButtonElement>(null);

  // Popover en position fixe : il échappe au défilement/clipping (modale) et passe au-dessus.
  const calculer = (): void => {
    const r = declencheur.current?.getBoundingClientRect();
    if (r) setPos({ top: r.bottom + 4, left: r.left, width: r.width });
  };

  useEffect(() => {
    if (!ouvert) return;
    const fermer = (e: MouseEvent): void => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOuvert(false);
    };
    const replacer = (): void => setOuvert(false);
    document.addEventListener('mousedown', fermer);
    window.addEventListener('scroll', replacer, true);
    window.addEventListener('resize', replacer);
    return () => {
      document.removeEventListener('mousedown', fermer);
      window.removeEventListener('scroll', replacer, true);
      window.removeEventListener('resize', replacer);
    };
  }, [ouvert]);

  const basculer = (): void => {
    if (!ouvert) calculer();
    setOuvert((o) => !o);
  };

  const courant = options.find((o) => o.valeur === valeur);
  const choisir = (v: string | null): void => {
    onChange(v);
    setOuvert(false);
  };

  return (
    <div className={styles.conteneur} ref={ref}>
      <button ref={declencheur} type="button" className={styles.champ} onClick={basculer}>
        <span className={courant ? styles.valeur : styles.placeholder}>
          {courant ? courant.libelle : placeholder}
        </span>
        <ChevronDown size={16} className={cx(styles.fleche, ouvert && styles.flecheOuverte)} />
      </button>

      {ouvert && pos !== null && (
        <ul
          className={styles.liste}
          style={{ position: 'fixed', top: pos.top, left: pos.left, width: pos.width }}
        >
          {permettreVide && (
            <li>
              <button type="button" className={styles.option} onClick={() => choisir(null)}>
                <span>{libelleVide}</span>
                {valeur === null && <Check size={15} />}
              </button>
            </li>
          )}
          {options.map((o) => (
            <li key={o.valeur}>
              <button
                type="button"
                className={cx(styles.option, o.valeur === valeur && styles.optionActive)}
                onClick={() => choisir(o.valeur)}
              >
                <span>{o.libelle}</span>
                {o.valeur === valeur && <Check size={15} />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

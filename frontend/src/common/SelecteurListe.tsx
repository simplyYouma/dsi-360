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
export function SelecteurListe({
  options,
  valeur,
  onChange,
  placeholder = 'Sélectionner…',
  permettreVide = false,
  libelleVide = 'Aucune',
}: Props): JSX.Element {
  const [ouvert, setOuvert] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const surClic = (e: MouseEvent): void => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOuvert(false);
    };
    document.addEventListener('mousedown', surClic);
    return () => document.removeEventListener('mousedown', surClic);
  }, []);

  const courant = options.find((o) => o.valeur === valeur);
  const choisir = (v: string | null): void => {
    onChange(v);
    setOuvert(false);
  };

  return (
    <div className={styles.conteneur} ref={ref}>
      <button type="button" className={styles.champ} onClick={() => setOuvert((o) => !o)}>
        <span className={courant ? styles.valeur : styles.placeholder}>
          {courant ? courant.libelle : placeholder}
        </span>
        <ChevronDown size={16} className={cx(styles.fleche, ouvert && styles.flecheOuverte)} />
      </button>

      {ouvert && (
        <ul className={styles.liste}>
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

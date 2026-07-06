import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, Check, Search } from 'lucide-react';
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
  /** Couleur sémantique par valeur : pastille dans la liste + badge teinté sur la sélection. */
  couleurs?: Record<string, string>;
}

/** Liste déroulante maison (popover) — aucun composant natif navigateur. */
interface Position {
  left: number;
  width: number;
  maxHeight: number;
  /** Ancrage : ouverture vers le bas (top) ou vers le haut (bottom). */
  top?: number;
  bottom?: number;
}

const MARGE = 4;
const ESPACE_MINI = 200;
// Au-delà de ce nombre d'options, on affiche un champ de recherche (filtre au clavier).
const SEUIL_RECHERCHE = 7;

export function SelecteurListe({
  options,
  valeur,
  onChange,
  placeholder = 'Sélectionner…',
  permettreVide = false,
  libelleVide = 'Aucune',
  couleurs,
}: Props): JSX.Element {
  const [ouvert, setOuvert] = useState(false);
  const [pos, setPos] = useState<Position | null>(null);
  const [filtre, setFiltre] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const declencheur = useRef<HTMLButtonElement>(null);

  const recherche = options.length > SEUIL_RECHERCHE;
  const optionsFiltrees = useMemo(() => {
    const q = filtre.trim().toLowerCase();
    if (q === '') return options;
    return options.filter((o) => o.libelle.toLowerCase().includes(q));
  }, [options, filtre]);

  // Popover en position fixe : il échappe au défilement/clipping (modale) et passe au-dessus.
  // Bascule vers le haut quand l'espace sous le champ est insuffisant (champ en bas de modale).
  const calculer = (): void => {
    const r = declencheur.current?.getBoundingClientRect();
    if (!r) return;
    const dessous = window.innerHeight - r.bottom;
    const dessus = r.top;
    const versHaut = dessous < ESPACE_MINI && dessus > dessous;
    if (versHaut) {
      setPos({
        left: r.left,
        width: r.width,
        bottom: window.innerHeight - r.top + MARGE,
        maxHeight: Math.max(160, dessus - 2 * MARGE),
      });
    } else {
      setPos({
        left: r.left,
        width: r.width,
        top: r.bottom + MARGE,
        maxHeight: Math.max(160, dessous - 2 * MARGE),
      });
    }
  };

  useEffect(() => {
    if (!ouvert) return;
    const fermer = (e: MouseEvent): void => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOuvert(false);
    };
    // Ne ferme que sur un scroll EXTÉRIEUR (le défilement interne au menu reste possible).
    const surScroll = (e: Event): void => {
      if (ref.current && ref.current.contains(e.target as Node)) return;
      setOuvert(false);
    };
    const surResize = (): void => setOuvert(false);
    document.addEventListener('mousedown', fermer);
    window.addEventListener('scroll', surScroll, true);
    window.addEventListener('resize', surResize);
    return () => {
      document.removeEventListener('mousedown', fermer);
      window.removeEventListener('scroll', surScroll, true);
      window.removeEventListener('resize', surResize);
    };
  }, [ouvert]);

  const basculer = (): void => {
    if (!ouvert) {
      setFiltre('');
      calculer();
    }
    setOuvert((o) => !o);
  };

  const courant = options.find((o) => o.valeur === valeur);
  const choisir = (v: string | null): void => {
    onChange(v);
    setFiltre('');
    setOuvert(false);
  };

  return (
    <div className={styles.conteneur} ref={ref}>
      <button ref={declencheur} type="button" className={styles.champ} onClick={basculer}>
        {courant && couleurs?.[courant.valeur] ? (
          <span
            className={styles.badge}
            style={{
              color: couleurs[courant.valeur],
              background: `color-mix(in srgb, ${couleurs[courant.valeur]} 14%, transparent)`,
            }}
          >
            {courant.libelle}
          </span>
        ) : (
          <span className={courant ? styles.valeur : styles.placeholder}>
            {courant ? courant.libelle : placeholder}
          </span>
        )}
        <ChevronDown size={16} className={cx(styles.fleche, ouvert && styles.flecheOuverte)} />
      </button>

      {ouvert && pos !== null && (
        <div
          className={styles.popover}
          style={{
            position: 'fixed',
            top: pos.top,
            bottom: pos.bottom,
            left: pos.left,
            width: pos.width,
            maxHeight: pos.maxHeight,
          }}
        >
          {recherche && (
            <div className={styles.rechercheZone}>
              <Search size={15} className={styles.rechercheIcone} />
              <input
                autoFocus
                className={styles.recherche}
                value={filtre}
                placeholder="Rechercher…"
                onChange={(e) => setFiltre(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    const premier = optionsFiltrees[0];
                    if (premier) choisir(premier.valeur);
                  } else if (e.key === 'Escape') {
                    setOuvert(false);
                  }
                }}
              />
            </div>
          )}
          <ul className={styles.liste}>
            {permettreVide && filtre.trim() === '' && (
              <li>
                <button type="button" className={styles.option} onClick={() => choisir(null)}>
                  <span>{libelleVide}</span>
                  {valeur === null && <Check size={15} />}
                </button>
              </li>
            )}
            {optionsFiltrees.map((o) => (
              <li key={o.valeur}>
                <button
                  type="button"
                  className={cx(styles.option, o.valeur === valeur && styles.optionActive)}
                  onClick={() => choisir(o.valeur)}
                >
                  <span className={styles.optionLibelle}>
                    {couleurs?.[o.valeur] && (
                      <span
                        className={styles.pastille}
                        style={{ background: couleurs[o.valeur] }}
                        aria-hidden="true"
                      />
                    )}
                    {o.libelle}
                  </span>
                  {o.valeur === valeur && <Check size={15} />}
                </button>
              </li>
            ))}
            {optionsFiltrees.length === 0 && <li className={styles.aucun}>Aucun résultat</li>}
          </ul>
        </div>
      )}
    </div>
  );
}

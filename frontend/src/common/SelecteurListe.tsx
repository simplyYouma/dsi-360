import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, Check, Plus, Search, Trash2, type LucideIcon } from 'lucide-react';
import { cx } from './cx';
import styles from './SelecteurListe.module.css';

export interface OptionListe {
  valeur: string;
  libelle: string;
  /** Option « vue » et non élément de la liste (Non assignés, DBS, Tous les agents…) : elle ne
   *  désigne personne en particulier, et se distingue donc visuellement des vrais choix. */
  special?: boolean;
  /** Cette entrée du référentiel peut être retirée d'ici (cf. `onSupprimer`). */
  supprimable?: boolean;
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
  /** Icône par valeur — remplace la pastille : une forme se lit plus vite qu'un point, et
   *  reste lisible pour qui distingue mal les couleurs. */
  icones?: Record<string, LucideIcon>;
  /** Grisé : la valeur reste lisible, le choix est fermé (ex. champ réservé à l'administrateur). */
  desactive?: boolean;
  /** Raison du grisage, en infobulle : on n'interdit jamais sans dire pourquoi. */
  titreDesactive?: string | undefined;
  /** Mot montré au survol quand une valeur est déjà choisie (ex. « Réassigner ») : on voit
   *  que la case est prise, et qu'un clic la remplace. */
  indiceReaffectation?: string;
  /** Action en pied de liste (ex. « Détenteur hors système… ») : le geste vit là où l'on
   *  cherche, plutôt qu'à côté du champ où il faut penser à le trouver. */
  action?: { libelle: string; icone?: LucideIcon; onClick: () => void };
  /** Enrichir le référentiel à la volée depuis le champ de recherche. Reçoit la saisie brute et
   *  rend la valeur à sélectionner — le serveur, lui, réécrit le libellé proprement.
   *  Sa présence force l'affichage du champ de recherche, quel que soit le nombre d'options. */
  onCreer?: (libelle: string) => Promise<string | null>;
  /** Retirer une entrée du référentiel, depuis la liste. N'apparaît que sur les options
   *  marquées `supprimable`. */
  onSupprimer?: (valeur: string) => Promise<void>;
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
// Largeur minimale du menu : assez pour lire les noms complets, même si le champ est étroit.
const LARGEUR_MINI = 240;
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
  icones,
  desactive = false,
  titreDesactive,
  indiceReaffectation,
  action,
  onCreer,
  onSupprimer,
}: Props): JSX.Element {
  const [ouvert, setOuvert] = useState(false);
  const [pos, setPos] = useState<Position | null>(null);
  const [filtre, setFiltre] = useState('');
  const [occupe, setOccupe] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const declencheur = useRef<HTMLButtonElement>(null);

  // Le champ de recherche est aussi le champ de saisie d'une nouvelle entrée : dès qu'on peut
  // créer, il est là — même sur une liste courte.
  const recherche = options.length > SEUIL_RECHERCHE || onCreer !== undefined;
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
    // Largeur au moins celle du champ, mais assez large pour lire les noms complets ; et on garde
    // le popover dans la fenêtre (jamais de débordement / scroll horizontal).
    const largeur = Math.min(Math.max(r.width, LARGEUR_MINI), window.innerWidth - 2 * MARGE);
    const left = Math.max(MARGE, Math.min(r.left, window.innerWidth - largeur - MARGE));
    if (versHaut) {
      setPos({
        left,
        width: largeur,
        bottom: window.innerHeight - r.top + MARGE,
        maxHeight: Math.max(160, dessus - 2 * MARGE),
      });
    } else {
      setPos({
        left,
        width: largeur,
        top: r.bottom + MARGE,
        maxHeight: Math.max(160, dessous - 2 * MARGE),
      });
    }
  };

  useEffect(() => {
    if (!ouvert) return;
    // Le popover est rendu en portal (hors `ref`) : on l'inclut dans le test de clic intérieur.
    const dedans = (n: Node): boolean =>
      (ref.current?.contains(n) ?? false) || (popoverRef.current?.contains(n) ?? false);
    const fermer = (e: MouseEvent): void => {
      if (!dedans(e.target as Node)) setOuvert(false);
    };
    // Ne ferme que sur un scroll EXTÉRIEUR (le défilement interne au menu reste possible).
    const surScroll = (e: Event): void => {
      if (dedans(e.target as Node)) return;
      setOuvert(false);
    };
    const surResize = (): void => setOuvert(false);
    // Capture : une modale stoppe la propagation du `mousedown` sur son contenu ; en phase bubble
    // le listener ne verrait jamais ces clics et le menu resterait ouvert. La capture les voit tous.
    document.addEventListener('mousedown', fermer, true);
    window.addEventListener('scroll', surScroll, true);
    window.addEventListener('resize', surResize);
    return () => {
      document.removeEventListener('mousedown', fermer, true);
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

  // Saisie qui ne correspond à aucune entrée : on propose de l'ajouter au référentiel.
  const saisie = filtre.trim();
  const inedit =
    onCreer !== undefined &&
    saisie.length >= 2 &&
    !options.some((o) => o.libelle.toLowerCase() === saisie.toLowerCase());

  const creer = async (): Promise<void> => {
    if (onCreer === undefined || !inedit || occupe) return;
    setOccupe(true);
    try {
      const nouvelle = await onCreer(saisie);
      if (nouvelle !== null) choisir(nouvelle);
    } finally {
      setOccupe(false);
    }
  };

  const supprimer = async (v: string): Promise<void> => {
    if (onSupprimer === undefined || occupe) return;
    setOccupe(true);
    try {
      await onSupprimer(v);
    } finally {
      setOccupe(false);
    }
  };

  // État coloré : le champ ENTIER prend la teinte du badge (fond, bordure, texte, chevron).
  const teinte = courant !== undefined ? couleurs?.[courant.valeur] : undefined;
  const IconeCourante = courant !== undefined ? icones?.[courant.valeur] : undefined;

  return (
    <div className={styles.conteneur} ref={ref}>
      <button
        ref={declencheur}
        type="button"
        className={cx(styles.champ, teinte !== undefined && styles.champTeinte)}
        style={
          teinte !== undefined
            ? {
                color: teinte,
                background: `color-mix(in srgb, ${teinte} 14%, var(--surface))`,
                borderColor: `color-mix(in srgb, ${teinte} 45%, transparent)`,
              }
            : undefined
        }
        onClick={basculer}
        disabled={desactive}
        title={desactive ? titreDesactive : undefined}
      >
        <span className={courant ? styles.valeur : styles.placeholder}>
          {IconeCourante !== undefined && (
            <IconeCourante size={14} className={styles.icone} aria-hidden="true" />
          )}
          {courant ? courant.libelle : placeholder}
        </span>
        {indiceReaffectation !== undefined && courant !== undefined && !desactive && (
          <span className={styles.indice}>{indiceReaffectation}</span>
        )}
        {!desactive && (
          <ChevronDown size={16} className={cx(styles.fleche, ouvert && styles.flecheOuverte)} />
        )}
      </button>

      {ouvert &&
        pos !== null &&
        createPortal(
          <div
            ref={popoverRef}
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
                      else if (inedit) void creer();
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
                  {/* « Tous les… » : une vue d'ensemble, jamais un élément de la liste. */}
                  <button
                    type="button"
                    className={cx(
                      styles.option,
                      styles.optionSpeciale,
                      optionsFiltrees[0]?.special !== true && styles.finSpeciales,
                    )}
                    onClick={() => choisir(null)}
                  >
                    <span>{libelleVide}</span>
                    {valeur === null && <Check size={15} />}
                  </button>
                </li>
              )}
              {optionsFiltrees.map((o, i) => {
                const Icone = icones?.[o.valeur];
                return (
                <li key={o.valeur} className={styles.ligne}>
                  <button
                    type="button"
                    className={cx(
                      styles.option,
                      o.special === true && styles.optionSpeciale,
                      // Trait sous la dernière option spéciale : les vues d'un côté, la liste de l'autre.
                      o.special === true &&
                        optionsFiltrees[i + 1]?.special !== true &&
                        styles.finSpeciales,
                      o.valeur === valeur && styles.optionActive,
                    )}
                    onClick={() => choisir(o.valeur)}
                  >
                    <span className={styles.optionLibelle}>
                      {/* L'icône prime sur la pastille : elle porte le sens, la couleur l'appuie. */}
                      {Icone !== undefined ? (
                        <Icone
                          size={15}
                          className={styles.icone}
                          style={{ color: couleurs?.[o.valeur] }}
                          aria-hidden="true"
                        />
                      ) : (
                        couleurs?.[o.valeur] && (
                          <span
                            className={styles.pastille}
                            style={{ background: couleurs[o.valeur] }}
                            aria-hidden="true"
                          />
                        )
                      )}
                      {o.libelle}
                    </span>
                    {o.valeur === valeur && <Check size={15} />}
                  </button>
                  {onSupprimer !== undefined && o.supprimable === true && (
                    <button
                      type="button"
                      className={styles.retirer}
                      title={`Retirer « ${o.libelle} » de la liste`}
                      aria-label={`Retirer ${o.libelle}`}
                      disabled={occupe}
                      onClick={(e) => {
                        e.stopPropagation();
                        void supprimer(o.valeur);
                      }}
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </li>
                );
              })}
              {optionsFiltrees.length === 0 && !inedit && (
                <li className={styles.aucun}>Aucun résultat</li>
              )}
              {inedit && (
                <li>
                  {/* Ajouter depuis l'endroit où l'on a cherché : le libellé sera réécrit
                      proprement par le serveur, pas laissé tel qu'il a été tapé. */}
                  <button
                    type="button"
                    className={cx(styles.option, styles.optionAction)}
                    disabled={occupe}
                    onClick={() => void creer()}
                  >
                    <span className={styles.optionLibelle}>
                      <Plus size={15} className={styles.icone} aria-hidden="true" />
                      Ajouter « {saisie} »
                    </span>
                  </button>
                </li>
              )}
              {action !== undefined && (
                <li>
                  <button
                    type="button"
                    className={cx(styles.option, styles.optionAction)}
                    onClick={() => {
                      setOuvert(false);
                      action.onClick();
                    }}
                  >
                    <span className={styles.optionLibelle}>
                      {action.icone !== undefined && (
                        <action.icone size={15} className={styles.icone} aria-hidden="true" />
                      )}
                      {action.libelle}
                    </span>
                  </button>
                </li>
              )}
            </ul>
          </div>,
          document.body,
        )}
    </div>
  );
}

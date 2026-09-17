import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, ChevronUp, Clock } from 'lucide-react';
import { cx } from '@/common/cx';
import { formatHeure } from './eodApi';
import styles from './SelecteurHeureEod.module.css';

interface Props {
  /** Heure déjà posée, pour placer le compteur (sinon : l'instant présent). */
  heures?: number | null;
  minutes?: number | null;
  /** Reçoit l'heure choisie — par « Maintenant » comme par le compteur, un seul chemin. */
  onChoisir: (heures: number, minutes: number) => void;
  /** Le déclencheur : bouton « Démarrer », champ « Heure de relance »… Rendu tel quel ; son clic
   *  ouvre le popover, il ne pose plus l'heure lui-même. */
  trigger: (props: { onClick: () => void; ref: React.RefObject<HTMLButtonElement> }) => ReactNode;
  desactive?: boolean;
}

const LARGEUR = 208;
/** Hauteur d'un cran du compteur : une seule valeur visible, les autres derrière, à la molette. */
const CRAN = 34;

/** Un compteur à roulette : une seule valeur visible, les voisines se rejoignent à la molette, au
 *  doigt ou aux flèches — sans barre de défilement, sans liste qui déroule. La roulette est une
 *  colonne qui défile réellement (donc l'inertie et le clavier viennent du navigateur), calée cran
 *  par cran ; c'est la position d'arrêt qui fait la valeur. */
function Roulette({
  valeurs,
  valeur,
  onChange,
  libelle,
}: {
  valeurs: number[];
  valeur: number;
  onChange: (v: number) => void;
  libelle: string;
}): JSX.Element {
  const piste = useRef<HTMLDivElement>(null);
  const arret = useRef<number | null>(null);

  // La piste s'ouvre déjà calée sur la valeur en cours, sans animation : on ne « voyage » pas
  // jusqu'à l'heure, on la trouve sous les yeux.
  useEffect(() => {
    const p = piste.current;
    if (p !== null && Math.round(p.scrollTop / CRAN) !== valeur) p.scrollTop = valeur * CRAN;
  }, [valeur]);

  // Le défilement s'arrête : le cran sous la fenêtre devient la valeur. On attend le calme
  // (150 ms sans mouvement) plutôt que de réagir à chaque pixel — la molette envoie des rafales.
  const surDefilement = (): void => {
    if (arret.current !== null) window.clearTimeout(arret.current);
    arret.current = window.setTimeout(() => {
      const p = piste.current;
      if (p === null) return;
      const cran = Math.max(0, Math.min(valeurs.length - 1, Math.round(p.scrollTop / CRAN)));
      if (cran !== valeur) onChange(cran);
    }, 150);
  };

  const pas = (delta: number): void => {
    const suivant = Math.max(0, Math.min(valeurs.length - 1, valeur + delta));
    onChange(suivant);
    if (piste.current !== null) piste.current.scrollTo({ top: suivant * CRAN, behavior: 'smooth' });
  };

  return (
    <div className={styles.roulette}>
      <button
        type="button"
        className={styles.cran}
        onClick={() => pas(-1)}
        aria-label={`${libelle} précédente`}
        tabIndex={-1}
      >
        <ChevronUp size={13} />
      </button>
      <div
        ref={piste}
        className={styles.piste}
        onScroll={surDefilement}
        role="spinbutton"
        aria-label={libelle}
        aria-valuemin={valeurs[0]}
        aria-valuemax={valeurs[valeurs.length - 1]}
        aria-valuenow={valeur}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'ArrowUp') {
            e.preventDefault();
            pas(-1);
          }
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            pas(1);
          }
        }}
      >
        {valeurs.map((v) => (
          <span key={v} className={cx(styles.valeur, v === valeur && styles.valeurChoisie)}>
            {String(v).padStart(2, '0')}
          </span>
        ))}
      </div>
      <button
        type="button"
        className={styles.cran}
        onClick={() => pas(1)}
        aria-label={`${libelle} suivante`}
        tabIndex={-1}
      >
        <ChevronDown size={13} />
      </button>
    </div>
  );
}

const HEURES = Array.from({ length: 24 }, (_, i) => i);
const MINUTES = Array.from({ length: 60 }, (_, i) => i);

/**
 * « Maintenant », ou une heure choisie — un popover discret, le même partout où l'EOD en a besoin
 * (démarrer ou terminer une étape, dater une relance d'agence).
 *
 * Une nuit se pointe en direct la plupart du temps : « Maintenant » reste donc le premier choix,
 * en tête, un clic. Mais elle ne se pointe pas toujours en direct — on rattrape une ligne oubliée,
 * on corrige une heure tapée trop vite — et c'est pour ce cas-là que deux compteurs à roulette
 * restent à portée juste en dessous, sans jamais s'imposer : une seule valeur visible chacun, les
 * autres derrière, à la molette.
 *
 * Il se ferme au moindre défilement de la page ou de la modale qui le porte : posé à l'écran par
 * coordonnées fixes, il resterait sinon planté là pendant que son déclencheur part avec la page.
 */
export function SelecteurHeureEod({
  heures = null,
  minutes = null,
  onChoisir,
  trigger,
  desactive = false,
}: Props): JSX.Element {
  const [ouvert, setOuvert] = useState(false);
  const [pos, setPos] = useState<CSSProperties | null>(null);
  const [h, setH] = useState(0);
  const [m, setM] = useState(0);
  const ref = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ouvert) return undefined;
    const surClic = (e: MouseEvent): void => {
      const n = e.target as Node;
      const dedans =
        (ref.current?.contains(n) ?? false) || (popoverRef.current?.contains(n) ?? false);
      if (!dedans) setOuvert(false);
    };
    // Tout défilement hors du popover le ferme — la page, le corps d'une modale — sauf celui
    // des roulettes elles-mêmes, qui est justement la façon de choisir. En phase de capture :
    // les évènements de défilement ne remontent pas.
    const surDefilement = (e: Event): void => {
      if (popoverRef.current?.contains(e.target as Node) ?? false) return;
      setOuvert(false);
    };
    document.addEventListener('mousedown', surClic);
    document.addEventListener('scroll', surDefilement, true);
    window.addEventListener('resize', surDefilement);
    return () => {
      document.removeEventListener('mousedown', surClic);
      document.removeEventListener('scroll', surDefilement, true);
      window.removeEventListener('resize', surDefilement);
    };
  }, [ouvert]);

  const ouvrir = (): void => {
    if (desactive) return;
    const maintenant = new Date();
    setH(heures ?? maintenant.getHours());
    setM(minutes ?? maintenant.getMinutes());
    const r = ref.current?.getBoundingClientRect();
    if (r) {
      const HAUTEUR = 190;
      const dessous = window.innerHeight - r.bottom;
      const left = Math.max(4, Math.min(r.left, window.innerWidth - LARGEUR - 4));
      setPos(
        dessous < HAUTEUR + 8 && r.top > dessous
          ? { position: 'fixed', bottom: window.innerHeight - r.top + 4, left }
          : { position: 'fixed', top: r.bottom + 4, left },
      );
    }
    setOuvert(true);
  };

  const choisir = (heures2: number, minutes2: number): void => {
    onChoisir(heures2, minutes2);
    setOuvert(false);
  };

  return (
    <>
      {trigger({ onClick: ouvrir, ref })}
      {ouvert &&
        pos !== null &&
        createPortal(
          <div ref={popoverRef} className={styles.popover} style={pos}>
            <button
              type="button"
              className={styles.maintenant}
              onClick={() => {
                const n = new Date();
                choisir(n.getHours(), n.getMinutes());
              }}
            >
              <Clock size={14} />
              Maintenant
            </button>

            <div className={styles.separateur}>
              <span>ou choisir</span>
            </div>

            <div className={styles.compteur}>
              <Roulette valeurs={HEURES} valeur={h} onChange={setH} libelle="Heure" />
              <span className={styles.lettre}>H</span>
              <Roulette valeurs={MINUTES} valeur={m} onChange={setM} libelle="Minute" />
              <button
                type="button"
                className={styles.valider}
                onClick={() => choisir(h, m)}
                title={`Valider ${formatHeure(h, m)}`}
              >
                OK
              </button>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}

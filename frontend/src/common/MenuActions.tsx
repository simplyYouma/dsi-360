import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { MoreHorizontal } from 'lucide-react';
import { cx } from './cx';
import styles from './MenuActions.module.css';

export interface ActionMenu {
  cle: string;
  libelle: string;
  icone?: ReactNode;
  danger?: boolean;
  onClick: () => void;
  masque?: boolean;
}

interface Props {
  actions: ActionMenu[];
  /** Libellé accessible du déclencheur (kebab). */
  etiquette?: string;
}

const MARGE = 4;
const LARGEUR = 210;

/** Menu d'actions déroulant (kebab) — popover en position fixe, aucun composant natif. */
export function MenuActions({ actions, etiquette = 'Actions' }: Props): JSX.Element {
  const [ouvert, setOuvert] = useState(false);
  const [pos, setPos] = useState<{ top?: number; bottom?: number; left: number } | null>(null);
  const declencheur = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  const visibles = actions.filter((a) => !a.masque);

  const calculer = (): void => {
    const r = declencheur.current?.getBoundingClientRect();
    if (!r) return;
    const dessous = window.innerHeight - r.bottom;
    const hauteurEstimee = visibles.length * 40 + 12;
    const versHaut = dessous < hauteurEstimee && r.top > dessous;
    // Aligne le bord droit du menu sur le bord droit du déclencheur, sans déborder de la fenêtre.
    const left = Math.max(MARGE, Math.min(r.right - LARGEUR, window.innerWidth - LARGEUR - MARGE));
    setPos(
      versHaut
        ? { bottom: window.innerHeight - r.top + MARGE, left }
        : { top: r.bottom + MARGE, left },
    );
  };

  useEffect(() => {
    if (!ouvert) return;
    const dedans = (n: Node): boolean =>
      (declencheur.current?.contains(n) ?? false) || (popoverRef.current?.contains(n) ?? false);
    const surClic = (e: MouseEvent): void => {
      if (!dedans(e.target as Node)) setOuvert(false);
    };
    const surScroll = (e: Event): void => {
      if (!dedans(e.target as Node)) setOuvert(false);
    };
    document.addEventListener('mousedown', surClic);
    window.addEventListener('scroll', surScroll, true);
    window.addEventListener('resize', () => setOuvert(false));
    return () => {
      document.removeEventListener('mousedown', surClic);
      window.removeEventListener('scroll', surScroll, true);
    };
  }, [ouvert]);

  const basculer = (): void => {
    if (!ouvert) calculer();
    setOuvert((o) => !o);
  };

  return (
    <div className={styles.conteneur}>
      <button
        ref={declencheur}
        type="button"
        className={cx(styles.kebab, ouvert && styles.kebabActif)}
        onClick={basculer}
        aria-label={etiquette}
        aria-haspopup="menu"
        aria-expanded={ouvert}
      >
        <MoreHorizontal size={17} />
      </button>

      {ouvert &&
        pos !== null &&
        createPortal(
          <div
            ref={popoverRef}
            className={styles.menu}
            role="menu"
            style={{
              position: 'fixed',
              top: pos.top,
              bottom: pos.bottom,
              left: pos.left,
              width: LARGEUR,
            }}
          >
            {visibles.map((a) => (
              <button
                key={a.cle}
                type="button"
                role="menuitem"
                className={cx(styles.item, a.danger && styles.itemDanger)}
                onClick={() => {
                  setOuvert(false);
                  a.onClick();
                }}
              >
                {a.icone && <span className={styles.itemIcone}>{a.icone}</span>}
                <span>{a.libelle}</span>
              </button>
            ))}
          </div>,
          document.body,
        )}
    </div>
  );
}

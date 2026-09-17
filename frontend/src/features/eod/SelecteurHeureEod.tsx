import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Check, Clock } from 'lucide-react';
import { cx } from '@/common/cx';
import { formatHeure } from './eodApi';
import styles from './SelecteurHeureEod.module.css';

interface Props {
  /** Heure déjà posée, pour préremplir le curseur du sélecteur (sinon : l'instant présent). */
  heures?: number | null;
  minutes?: number | null;
  /** Reçoit l'heure choisie — par « Maintenant » comme par le sélecteur, un seul chemin. */
  onChoisir: (heures: number, minutes: number) => void;
  /** Le déclencheur : bouton « Démarrer », champ « Heure de relance »… Rendu tel quel ; son clic
   *  ouvre le popover, il ne pose plus l'heure lui-même. */
  trigger: (props: { onClick: () => void; ref: React.RefObject<HTMLButtonElement> }) => ReactNode;
  desactive?: boolean;
}

const HEURES = Array.from({ length: 24 }, (_, i) => i);
const MINUTES = Array.from({ length: 60 }, (_, i) => i);
const LARGEUR = 240;

/**
 * « Maintenant », ou une heure choisie — un popover discret, le même partout où l'EOD en a besoin
 * (démarrer une étape, dater une relance d'agence).
 *
 * Une nuit se pointe en direct la plupart du temps : « Maintenant » reste donc le premier choix,
 * gros, en tête du popover, un clic après l'avoir ouvert. Mais elle ne se pointe pas toujours en
 * direct — on rattrape une ligne oubliée, on corrige une heure de relance tapée trop vite — et
 * c'est pour ce cas-là que les deux colonnes, heures et minutes, restent à portée juste en dessous,
 * sans jamais s'imposer.
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
  const colH = useRef<HTMLDivElement>(null);
  const colM = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const surClic = (e: MouseEvent): void => {
      const n = e.target as Node;
      const dedans =
        (ref.current?.contains(n) ?? false) || (popoverRef.current?.contains(n) ?? false);
      if (!dedans) setOuvert(false);
    };
    document.addEventListener('mousedown', surClic);
    return () => document.removeEventListener('mousedown', surClic);
  }, []);

  const ouvrir = (): void => {
    const maintenant = new Date();
    setH(heures ?? maintenant.getHours());
    setM(minutes ?? maintenant.getMinutes());
    const r = ref.current?.getBoundingClientRect();
    if (r) {
      const dessous = window.innerHeight - r.bottom;
      const left = Math.max(4, Math.min(r.left, window.innerWidth - LARGEUR - 4));
      setPos(
        dessous < 260 && r.top > dessous
          ? { position: 'fixed', bottom: window.innerHeight - r.top + 4, left }
          : { position: 'fixed', top: r.bottom + 4, left },
      );
    }
    setOuvert(true);
  };

  // La colonne s'ouvre déjà défilée sur la valeur en cours : sans quoi choisir « 23H » depuis
  // « 00H » demande vingt-trois clics avant même de commencer à corriger la minute.
  useEffect(() => {
    if (!ouvert) return;
    requestAnimationFrame(() => {
      colH.current?.querySelector(`[data-valeur="${h}"]`)?.scrollIntoView({ block: 'center' });
      colM.current?.querySelector(`[data-valeur="${m}"]`)?.scrollIntoView({ block: 'center' });
    });
    // Volontairement une seule fois à l'ouverture : redéfiler à chaque clic dans la colonne
    // ramènerait la vue sous le doigt qui vient justement de cliquer plus loin.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ouvert]);

  const choisir = (heures2: number, minutes2: number): void => {
    onChoisir(heures2, minutes2);
    setOuvert(false);
  };

  return (
    <>
      {trigger({ onClick: ouvrir, ref })}
      {ouvert &&
        pos !== null &&
        !desactive &&
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
              <Clock size={15} />
              Maintenant
            </button>

            <div className={styles.separateur}>
              <span>ou choisir l’heure</span>
            </div>

            <div className={styles.colonnes}>
              <div ref={colH} className={styles.colonne}>
                {HEURES.map((v) => (
                  <button
                    type="button"
                    key={v}
                    data-valeur={v}
                    className={cx(styles.valeur, v === h && styles.valeurChoisie)}
                    onClick={() => setH(v)}
                  >
                    {v === h && <Check size={11} className={styles.coche} />}
                    {String(v).padStart(2, '0')}
                  </button>
                ))}
              </div>
              <span className={styles.lettre}>H</span>
              <div ref={colM} className={styles.colonne}>
                {MINUTES.map((v) => (
                  <button
                    type="button"
                    key={v}
                    data-valeur={v}
                    className={cx(styles.valeur, v === m && styles.valeurChoisie)}
                    onClick={() => setM(v)}
                  >
                    {v === m && <Check size={11} className={styles.coche} />}
                    {String(v).padStart(2, '0')}
                  </button>
                ))}
              </div>
            </div>

            <button type="button" className={styles.valider} onClick={() => choisir(h, m)}>
              Valider {formatHeure(h, m)}
            </button>
          </div>,
          document.body,
        )}
    </>
  );
}

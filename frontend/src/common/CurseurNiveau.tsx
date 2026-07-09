import { useRef } from 'react';
import type { KeyboardEvent, PointerEvent } from 'react';
import { cx } from './cx';
import styles from './CurseurNiveau.module.css';

const MOTS = ['Très faible', 'Faible', 'Moyen', 'Élevé', 'Critique'];
const NIVEAUX = [1, 2, 3, 4, 5];

/** Couleur par bande ITIL (1-2 faible, 3 moyen, 4-5 élevé) : la couleur porte le sens,
 *  au lieu d'un dégradé arc-en-ciel décoratif. */
function couleurBande(valeur: number): string {
  if (valeur <= 2) return 'var(--status-ok)';
  if (valeur === 3) return 'var(--status-warn)';
  return 'var(--status-danger)';
}

interface CurseurNiveauProps {
  valeur: number; // 1..5
  onChange: (n: number) => void;
}

/** Sélecteur de niveau 1→5 : cinq segments de hauteur croissante. Maison, zéro composant natif. */
export function CurseurNiveau({ valeur, onChange }: CurseurNiveauProps): JSX.Element {
  const piste = useRef<HTMLDivElement>(null);
  const couleur = couleurBande(valeur);

  const depuisX = (clientX: number): void => {
    const el = piste.current;
    if (el === null) return;
    const r = el.getBoundingClientRect();
    const ratio = (clientX - r.left) / r.width;
    onChange(Math.min(5, Math.max(1, Math.ceil(ratio * 5))));
  };

  const surTouche = (e: KeyboardEvent): void => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowUp') onChange(Math.min(5, valeur + 1));
    if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') onChange(Math.max(1, valeur - 1));
  };

  const surPointe = (e: PointerEvent): void => {
    e.currentTarget.setPointerCapture(e.pointerId);
    depuisX(e.clientX);
  };

  return (
    <div className={styles.bloc}>
      <div
        ref={piste}
        className={styles.segments}
        onPointerDown={surPointe}
        onPointerMove={(e) => {
          if (e.buttons === 1) depuisX(e.clientX);
        }}
        onKeyDown={surTouche}
        role="slider"
        tabIndex={0}
        aria-valuemin={1}
        aria-valuemax={5}
        aria-valuenow={valeur}
        aria-valuetext={`${valeur} · ${MOTS[valeur - 1] ?? ''}`}
      >
        {NIVEAUX.map((n) => (
          <span
            key={n}
            className={cx(styles.segment, n <= valeur && styles.actif)}
            style={n <= valeur ? { background: couleur } : undefined}
            aria-hidden="true"
          />
        ))}
      </div>
      <span className={styles.etiquette} style={{ color: couleur }}>
        <span className={styles.chiffre}>{valeur}</span>
        {MOTS[valeur - 1] ?? ''}
      </span>
    </div>
  );
}

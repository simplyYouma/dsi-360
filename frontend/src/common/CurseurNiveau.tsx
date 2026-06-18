import { useRef } from 'react';
import type { KeyboardEvent, PointerEvent } from 'react';
import styles from './CurseurNiveau.module.css';

const COULEURS = ['#1f9d55', '#7fc81f', '#e0a341', '#e07a3c', '#d64545'];
const MOTS = ['Très faible', 'Faible', 'Moyen', 'Élevé', 'Critique'];

interface CurseurNiveauProps {
  valeur: number; // 1..5
  onChange: (n: number) => void;
}

/** Curseur maison 1→5 avec piste en dégradé de gravité (vert → rouge). Pas de composant natif. */
export function CurseurNiveau({ valeur, onChange }: CurseurNiveauProps): JSX.Element {
  const piste = useRef<HTMLDivElement>(null);
  const couleur = COULEURS[valeur - 1] ?? '#888';
  const position = ((valeur - 1) / 4) * 100;

  const depuisX = (clientX: number): void => {
    const el = piste.current;
    if (el === null) return;
    const r = el.getBoundingClientRect();
    const ratio = (clientX - r.left) / r.width;
    onChange(Math.min(5, Math.max(1, Math.round(ratio * 4) + 1)));
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
        className={styles.piste}
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
      >
        <span className={styles.curseur} style={{ left: `${position}%`, borderColor: couleur }} />
      </div>
      <span className={styles.etiquette} style={{ color: couleur }}>
        {valeur} · {MOTS[valeur - 1] ?? ''}
      </span>
    </div>
  );
}

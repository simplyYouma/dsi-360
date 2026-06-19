import { useEffect, useId, useState } from 'react';
import styles from './SablierSla.module.css';

interface Props {
  echeance: string | null; // sla_resolution_le (ISO)
  debut: string; // cree_le (ISO) — base de l'écoulement
  statut: 'a_lheure' | 'approche' | 'depasse';
}

const COULEUR: Record<Props['statut'], string> = {
  a_lheure: 'var(--status-ok)',
  approche: 'var(--status-warn)',
  depasse: 'var(--status-danger)',
};

// Silhouette du sablier (bouteilles haut/bas), pour découper le sable proprement.
const SILHOUETTE = 'M5 3 H19 L12.6 12 L19 21 H5 L11.4 12 Z';
const HAUT = 8.6; // hauteur utile d'une ampoule (y 3.4 -> 12 et 12 -> 20.6)

function duree(ms: number): string {
  const minutes = Math.floor(ms / 60000);
  const heures = Math.floor(minutes / 60);
  const jours = Math.floor(heures / 24);
  if (jours >= 1) return `${jours} j`;
  if (heures >= 1) return `${heures} h`;
  return `${Math.max(1, minutes)} min`;
}

/** Libellé non ambigu : « reste 4 j » ou « Dépassé · 2 j ». */
function libelleSla(restantMs: number): string {
  return restantMs <= 0 ? `Dépassé · ${duree(-restantMs)}` : `reste ${duree(restantMs)}`;
}

/** Sablier réaliste : niveau de sable continu (écoulé création -> échéance) découpé dans la
 *  silhouette pour rester lisible, couleur d'urgence vert / orange / rouge. */
export function SablierSla({ echeance, debut, statut }: Props): JSX.Element {
  const clip = useId();
  const [, rafraichir] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => rafraichir((t) => t + 1), 30000);
    return () => window.clearInterval(id);
  }, []);

  if (echeance === null) return <span className={styles.na}>—</span>;

  const fin = new Date(echeance).getTime();
  const dep = new Date(debut).getTime();
  const restant = fin - Date.now();
  const total = Math.max(1, fin - dep);
  const reste = Math.max(0, Math.min(1, restant / total)); // part encore en haut
  const ecoule = 1 - reste; // part tombée en bas
  const couleur = COULEUR[statut];

  return (
    <span className={styles.sablier} title={`SLA : ${libelleSla(restant)}`}>
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
        <defs>
          <clipPath id={clip}>
            <path d={SILHOUETTE} />
          </clipPath>
        </defs>
        <g clipPath={`url(#${clip})`}>
          <rect x="0" y="0" width="24" height="24" fill="var(--bg-subtle)" />
          {/* Sable en haut : posé au-dessus du goulot, hauteur = part restante. */}
          {reste > 0.01 && (
            <rect x="0" y={12 - reste * HAUT} width="24" height={reste * HAUT} fill={couleur} />
          )}
          {/* Tas en bas : monte depuis la base, hauteur = part écoulée. */}
          {ecoule > 0.01 && (
            <rect x="0" y={20.6 - ecoule * HAUT} width="24" height={ecoule * HAUT} fill={couleur} />
          )}
        </g>
        <path d={SILHOUETTE} fill="none" stroke={couleur} strokeWidth="1.3" strokeLinejoin="round" />
        <path d="M6 3 H18 M6 21 H18" stroke={couleur} strokeWidth="1.6" strokeLinecap="round" />
        {/* Filet de sable qui tombe au goulot tant qu'il s'écoule. */}
        {reste > 0.02 && ecoule > 0.02 && (
          <line x1="12" y1="11.5" x2="12" y2="14" stroke={couleur} strokeWidth="0.9" strokeLinecap="round">
            <animate attributeName="opacity" values="1;0.15;1" dur="1s" repeatCount="indefinite" />
          </line>
        )}
      </svg>
      <span className={styles.reste} style={{ color: couleur }}>
        {libelleSla(restant)}
      </span>
    </span>
  );
}

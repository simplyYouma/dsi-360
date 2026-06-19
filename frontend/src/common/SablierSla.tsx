import { useEffect, useState } from 'react';
import styles from './SablierSla.module.css';

interface Props {
  echeance: string | null; // sla_resolution_le (ISO)
  debut: string; // cree_le (ISO)
  statut: 'a_lheure' | 'approche' | 'depasse';
}

const COULEUR: Record<Props['statut'], string> = {
  a_lheure: 'var(--status-ok)',
  approche: 'var(--status-warn)',
  depasse: 'var(--status-danger)',
};

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

/** Sablier réaliste : le sable s'écoule du haut vers le bas au fil du temps écoulé entre la
 *  création et l'échéance. Plein en haut à la création, vide (et rouge) à l'échéance dépassée. */
export function SablierSla({ echeance, debut, statut }: Props): JSX.Element {
  const [, rafraichir] = useState(0);

  // Le sable « tombe » visuellement au fil du temps (page ouverte).
  useEffect(() => {
    const id = window.setInterval(() => rafraichir((t) => t + 1), 30000);
    return () => window.clearInterval(id);
  }, []);

  if (echeance === null) return <span className={styles.na}>—</span>;

  const fin = new Date(echeance).getTime();
  const dep = new Date(debut).getTime();
  const maintenant = Date.now();
  const restant = fin - maintenant;
  const total = Math.max(1, fin - dep);
  // Part de sable encore en haut = temps restant / durée totale création -> échéance.
  const reste = Math.max(0, Math.min(1, restant / total));
  const couleur = COULEUR[statut];

  // Sable du haut : triangle dont l'apex est au goulot (12,12), base vers le haut.
  const hautHaut = 12 - reste * 8;
  const demiHaut = reste * 6.5;
  const sableHaut = `12,12 ${12 - demiHaut},${hautHaut} ${12 + demiHaut},${hautHaut}`;
  // Tas de sable en bas : grandit à mesure que le temps s'écoule.
  const ecoule = 1 - reste;
  const hautBas = 20 - ecoule * 8;
  const demiBas = ecoule * 6.5;
  const sableBas = `${12 - demiBas},20 ${12 + demiBas},20 12,${hautBas}`;

  return (
    <span className={styles.sablier} title={`SLA : ${libelleSla(restant)}`}>
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <g stroke={couleur} strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d="M6 3 h12" />
          <path d="M6 21 h12" />
          <path d="M7 3 v3 L12 12 L7 18 v3" />
          <path d="M17 3 v3 L12 12 L17 18 v3" />
        </g>
        {reste > 0.02 && <polygon points={sableHaut} fill={couleur} />}
        {ecoule > 0.02 && <polygon points={sableBas} fill={couleur} opacity={0.5} />}
        {/* Filet de sable qui tombe au goulot, tant qu'il s'écoule encore. */}
        {reste > 0.02 && ecoule > 0.02 && (
          <line x1="12" y1="11" x2="12" y2="14" stroke={couleur} strokeWidth="1" strokeLinecap="round">
            <animate attributeName="opacity" values="1;0.2;1" dur="1.1s" repeatCount="indefinite" />
          </line>
        )}
      </svg>
      <span className={styles.reste} style={{ color: couleur }}>
        {libelleSla(restant)}
      </span>
    </span>
  );
}

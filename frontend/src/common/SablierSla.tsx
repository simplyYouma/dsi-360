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

function texteRestant(restantMs: number): string {
  if (restantMs <= 0) return 'Dépassé';
  const minutes = Math.floor(restantMs / 60000);
  const heures = Math.floor(minutes / 60);
  const jours = Math.floor(heures / 24);
  if (jours >= 1) return `${jours} j`;
  if (heures >= 1) return `${heures} h`;
  return `${Math.max(1, minutes)} min`;
}

/** Sablier SVG dont le sable s'écoule en temps réel selon le délai SLA restant. */
export function SablierSla({ echeance, debut, statut }: Props): JSX.Element {
  const [, rafraichir] = useState(0);

  // Tick régulier : le sable « descend » visuellement au fil du temps (page ouverte).
  useEffect(() => {
    const id = window.setInterval(() => rafraichir((t) => t + 1), 30000);
    return () => window.clearInterval(id);
  }, []);

  if (echeance === null) return <span className={styles.na}>—</span>;

  const fin = new Date(echeance).getTime();
  const dep = new Date(debut).getTime();
  const restant = fin - Date.now();
  const total = Math.max(1, fin - dep);
  // Part de sable encore en haut (1 = plein, 0 = écoulé).
  const reste = Math.max(0, Math.min(1, restant / total));
  const couleur = COULEUR[statut];

  // Triangle de sable haut (apex au goulot 12,12) et tas de sable bas.
  const hautHaut = 12 - reste * 8;
  const demiHaut = reste * 6.5;
  const sableHaut = `12,12 ${12 - demiHaut},${hautHaut} ${12 + demiHaut},${hautHaut}`;
  const ecoule = 1 - reste;
  const hautBas = 20 - ecoule * 8;
  const demiBas = ecoule * 6.5;
  // Tas de sable en bas : triangle dont l'apex monte au fil de l'écoulement.
  const sableBas = `${12 - demiBas},20 ${12 + demiBas},20 12,${hautBas}`;

  return (
    <span className={styles.sablier} title={`SLA : ${texteRestant(restant)}`}>
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
        <g stroke={couleur} strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d="M6 3 h12" />
          <path d="M6 21 h12" />
          <path d="M7 3 v3 L12 12 L7 18 v3" />
          <path d="M17 3 v3 L12 12 L17 18 v3" />
        </g>
        {reste > 0.02 && <polygon points={sableHaut} fill={couleur} />}
        {ecoule > 0.02 && <polygon points={sableBas} fill={couleur} opacity={0.55} />}
      </svg>
      <span className={styles.reste} style={{ color: couleur }}>
        {texteRestant(restant)}
      </span>
    </span>
  );
}

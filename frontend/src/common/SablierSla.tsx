import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import styles from './SablierSla.module.css';

interface Props {
  echeance: string | null; // sla_resolution_le (ISO)
  statut: 'a_lheure' | 'approche' | 'depasse';
  priorite: number | null;
}

const COULEUR: Record<Props['statut'], string> = {
  a_lheure: 'var(--status-ok)',
  approche: 'var(--status-warn)',
  depasse: 'var(--status-danger)',
};

// Cibles de résolution (minutes) par priorité, chargées une fois et mises en cache.
let _ciblesCache: Record<number, number> | null = null;
let _promesse: Promise<Record<number, number>> | null = null;

function chargerCibles(): Promise<Record<number, number>> {
  if (_ciblesCache) return Promise.resolve(_ciblesCache);
  if (_promesse === null) {
    _promesse = api
      .get<{ priorite: number; resolution_minutes: number }[]>('/referentiels/sla')
      .then((regles) => {
        _ciblesCache = Object.fromEntries(regles.map((r) => [r.priorite, r.resolution_minutes]));
        return _ciblesCache;
      });
  }
  return _promesse;
}

function duree(ms: number): string {
  const minutes = Math.floor(ms / 60000);
  const heures = Math.floor(minutes / 60);
  const jours = Math.floor(heures / 24);
  if (jours >= 1) return `${jours} j`;
  if (heures >= 1) return `${heures} h`;
  return `${Math.max(1, minutes)} min`;
}

/** Libellé explicite : « reste 4 j » ou « Dépassé · 2 j » (lève toute ambiguïté). */
function libelleSla(restantMs: number): string {
  return restantMs <= 0 ? `Dépassé · ${duree(-restantMs)}` : `reste ${duree(restantMs)}`;
}

/** Sablier dont le sable reflète le temps restant rapporté à la CIBLE SLA de la priorité.
 *  Plein = une fenêtre SLA entière devant soi ; vide = échéance atteinte ; rouge = dépassé. */
export function SablierSla({ echeance, statut, priorite }: Props): JSX.Element {
  const [cibles, setCibles] = useState<Record<number, number> | null>(_ciblesCache);
  const [, rafraichir] = useState(0);

  useEffect(() => {
    if (cibles === null) void chargerCibles().then(setCibles);
    const id = window.setInterval(() => rafraichir((t) => t + 1), 30000);
    return () => window.clearInterval(id);
  }, [cibles]);

  const cibleMin = priorite !== null ? cibles?.[priorite] : undefined;
  if (echeance === null || cibleMin === undefined) return <span className={styles.na}>—</span>;

  const restant = new Date(echeance).getTime() - Date.now();
  // Part de sable restante = temps restant / fenêtre SLA cible (bornée 0..1).
  const reste = Math.max(0, Math.min(1, restant / (cibleMin * 60000)));
  const couleur = COULEUR[statut];

  const hautHaut = 12 - reste * 8;
  const demiHaut = reste * 6.5;
  const sableHaut = `12,12 ${12 - demiHaut},${hautHaut} ${12 + demiHaut},${hautHaut}`;
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
      </svg>
      <span className={styles.reste} style={{ color: couleur }}>
        {libelleSla(restant)}
      </span>
    </span>
  );
}

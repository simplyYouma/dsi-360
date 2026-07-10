import { useEffect, useState } from 'react';
import { Clock } from 'lucide-react';
import { BadgePriorite } from './statuts';
import { api } from '@/lib/api';
import styles from './ApercuEcheance.module.css';

interface RegleSla {
  priorite: number;
  prise_en_charge_minutes: number;
  resolution_minutes: number;
}

interface Props {
  impact: number;
  urgence: number;
  /** Module concerné : les cibles SLA sont propres à chaque module. */
  module: string;
}

// Matrice de priorité ITIL (SI-12.01) — miroir exact du backend (domain/activite.py).
const MATRICE_PRIORITE: Record<string, number> = {
  '3,3': 1,
  '3,2': 2,
  '3,1': 3,
  '2,3': 2,
  '2,2': 3,
  '2,1': 4,
  '1,3': 3,
  '1,2': 4,
  '1,1': 5,
};
const bande = (n: number): number => (n >= 4 ? 3 : n === 3 ? 2 : 1);

/** Priorité P1..P5 selon la matrice ITIL impact × urgence (miroir du backend). */
function calculerPriorite(impact: number, urgence: number): number {
  return MATRICE_PRIORITE[`${bande(impact)},${bande(urgence)}`] ?? 3;
}

function formaterDuree(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  if (minutes < 60 * 24) {
    const h = minutes / 60;
    return `${Number.isInteger(h) ? h : h.toFixed(1)} h`;
  }
  const j = minutes / (60 * 24);
  return `${Number.isInteger(j) ? j : j.toFixed(1)} j`;
}

function formaterEcheance(minutes: number): string {
  const d = new Date(Date.now() + minutes * 60000);
  return d.toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Aperçu en temps réel de la priorité et des échéances SLA (prise en charge / résolution) déduites
 *  d'impact × urgence, d'après la matrice SLA paramétrée. Purement indicatif : le calcul fait foi
 *  côté serveur à la création. */
export function ApercuEcheance({ impact, urgence, module }: Props): JSX.Element {
  const [matrice, setMatrice] = useState<Record<number, RegleSla>>({});

  useEffect(() => {
    void api
      .get<RegleSla[]>(`/referentiels/sla?module=${module}`)
      .then((regles) => setMatrice(Object.fromEntries(regles.map((r) => [r.priorite, r]))))
      .catch(() => setMatrice({}));
  }, [module]);

  const priorite = calculerPriorite(impact, urgence);
  const regle = matrice[priorite];

  return (
    <div className={styles.apercu}>
      <div className={styles.tete}>
        <Clock size={14} className={styles.icone} />
        <span className={styles.label}>
          Priorité &amp; échéances SLA (calculées automatiquement)
        </span>
        <BadgePriorite priorite={priorite} />
      </div>
      {regle ? (
        <div className={styles.cibles}>
          <span>
            Prise en charge sous <strong>{formaterDuree(regle.prise_en_charge_minutes)}</strong>
          </span>
          <span>
            Résolution sous <strong>{formaterDuree(regle.resolution_minutes)}</strong>
            <span className={styles.date}>
              {' '}
              · échéance ≈ {formaterEcheance(regle.resolution_minutes)}
            </span>
          </span>
        </div>
      ) : (
        <span className={styles.date}>Cibles SLA indisponibles pour cette priorité.</span>
      )}
    </div>
  );
}

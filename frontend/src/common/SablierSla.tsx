import { useEffect, useId, useState } from 'react';
import { cx } from './cx';
import styles from './SablierSla.module.css';

/** État du délai. « termine » n'est pas un verdict : c'est l'absence de délai qui court encore. */
export type EtatSla = 'a_lheure' | 'approche' | 'depasse' | 'termine';

interface Props {
  echeance: string | null; // date d'échéance (ISO)
  debut?: string | null; // base de l'écoulement (création…) ; par défaut, 14 j avant l'échéance
  /** État imposé ; sinon déduit du temps restant (approche < 48 h, dépassé si négatif). */
  statut?: EtatSla;
  /** Activité terminée : le compteur ne court plus. Le sablier se fige, sans battement ni sable
   *  qui tombe, et n'annonce plus qu'un fait — « Terminé ». */
  arrete?: boolean;
}

const COULEUR: Record<EtatSla, string> = {
  a_lheure: 'var(--status-ok)',
  approche: 'var(--status-warn)',
  depasse: 'var(--status-danger)',
  // Terminé : le délai ne court plus. Neutre — ce n'est ni un succès ni une alerte, c'est fini.
  termine: 'var(--text-muted)',
};

// Un seul battement pour toute la page. Une liste de quinze tickets, c'est quinze sabliers : un
// minuteur chacun les ferait battre en désordre, et pour rien — le temps est le même pour tous.
const abonnes = new Set<() => void>();
let minuteur: number | null = null;

// `actif` : un sablier figé (activité terminée) ne s'abonne pas — inutile de le réveiller chaque
// seconde, son temps ne bouge plus.
function useBattement(actif: boolean): void {
  const [, rafraichir] = useState(0);
  useEffect(() => {
    if (!actif) return;
    const reveiller = (): void => rafraichir((n) => n + 1);
    abonnes.add(reveiller);
    minuteur ??= window.setInterval(() => abonnes.forEach((f) => f()), 1000);
    return () => {
      abonnes.delete(reveiller);
      if (abonnes.size === 0 && minuteur !== null) {
        window.clearInterval(minuteur);
        minuteur = null;
      }
    };
  }, [actif]);
}

// Deux ampoules bombées qui se rejoignent au goulot (12, 12). Le sable prend la forme du verre :
// on le dessine large, on le découpe dedans.
const AMPOULE_HAUT = 'M5.3 3.4 C5.3 7.9 8.7 10.3 12 12 C15.3 10.3 18.7 7.9 18.7 3.4 Z';
const AMPOULE_BAS = 'M5.3 20.6 C5.3 16.1 8.7 13.7 12 12 C15.3 13.7 18.7 16.1 18.7 20.6 Z';

const HAUT_Y = 3.4; // sommet de l'ampoule supérieure
const BAS_Y = 20.6; // fond de l'ampoule inférieure
const GOULOT = 12;
const HAUTEUR = GOULOT - HAUT_Y; // course du sable dans une ampoule

function duree(ms: number): string {
  const minutes = Math.floor(ms / 60000);
  const heures = Math.floor(minutes / 60);
  const jours = Math.floor(heures / 24);
  if (jours >= 1) return `${jours} j`;
  if (heures >= 1) return `${heures} h`;
  return `${Math.max(1, minutes)} min`;
}

function formaterEcheance(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

/** Le sable du haut repose sur le goulot et se creuse en entonnoir à mesure qu'il s'écoule :
 *  c'est ce creux qui donne à l'œil la sensation qu'il descend. */
function sableHaut(part: number): string {
  const hauteur = part * HAUTEUR;
  const y = GOULOT - hauteur;
  const creux = Math.min(1.7, hauteur * 0.5); // s'efface quand il ne reste qu'un fond
  return `M2 ${y} Q12 ${y + creux * 2} 22 ${y} L22 ${GOULOT} L2 ${GOULOT} Z`;
}

/** En bas, le sable ne s'empile pas à plat : il forme un monticule sous le filet. */
function sableBas(part: number): string {
  const hauteur = part * HAUTEUR;
  const y = BAS_Y - hauteur;
  const cone = Math.min(2.2, hauteur * 0.7);
  return `M2 ${BAS_Y} L2 ${y} Q12 ${y - cone * 2} 22 ${y} L22 ${BAS_Y} Z`;
}

/** Sablier du SLA : le sable descend au fil du temps, la couleur dit l'urgence. */
const JOUR = 86_400_000;

export function SablierSla({ echeance, debut, statut, arrete }: Props): JSX.Element {
  const clipHaut = useId();
  const clipBas = useId();
  const gele = arrete === true || statut === 'termine';
  useBattement(!gele && echeance !== null);

  if (echeance === null) return <span className={styles.na}>—</span>;

  const fin = new Date(echeance).getTime();
  // Sans début fourni (tâches, jalons…), on prend une fenêtre de 14 j : le sablier reste parlant.
  const depart = debut ? new Date(debut).getTime() : fin - 14 * JOUR;
  const restant = fin - Date.now();
  // État déduit si non imposé : dépassé (< 0), approche (< 48 h), sinon à l'heure.
  const etat: EtatSla =
    statut ?? (restant < 0 ? 'depasse' : restant < 2 * JOUR ? 'approche' : 'a_lheure');
  const total = Math.max(1, fin - depart);
  // Figé : le sable est au repos (tout tombé), plus rien ne coule. Sinon, proportion du temps.
  const reste = gele ? 0 : Math.max(0, Math.min(1, restant / total)); // ce qui est encore en haut
  const ecoule = 1 - reste; // ce qui est tombé
  const couleur = COULEUR[etat];
  const coule = !gele && reste > 0.005 && ecoule > 0.005;
  // « Dépassé » n'a de sens que sur un dossier vivant : sur une activité terminée, il laisserait
  // croire que le délai tourne encore. On n'annonce alors que le fait — l'activité est close.
  const enRetard = !gele && etat === 'depasse';
  const libelle = gele
    ? `${formaterEcheance(echeance)} · Terminé`
    : enRetard
      ? `${formaterEcheance(echeance)} · Dépassé · ${duree(-restant)}`
      : formaterEcheance(echeance);
  const infobulle = gele
    ? `Échéance ${formaterEcheance(echeance)} — le SLA ne court plus (activité terminée).`
    : `Échéance : ${libelle}`;

  return (
    <span className={cx(styles.sablier, gele && styles.gele)} title={infobulle}>
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
        <defs>
          <clipPath id={clipHaut}>
            <path d={AMPOULE_HAUT} />
          </clipPath>
          <clipPath id={clipBas}>
            <path d={AMPOULE_BAS} />
          </clipPath>
        </defs>

        {/* Le verre vide, à peine teinté : sans lui, le sable flotterait. */}
        <path d={AMPOULE_HAUT} fill="var(--bg-subtle)" />
        <path d={AMPOULE_BAS} fill="var(--bg-subtle)" />

        {reste > 0.005 && (
          <g clipPath={`url(#${clipHaut})`}>
            <path d={sableHaut(reste)} fill={couleur} className={styles.sable} />
          </g>
        )}
        {ecoule > 0.005 && (
          <g clipPath={`url(#${clipBas})`}>
            <path d={sableBas(ecoule)} fill={couleur} className={styles.sable} />
          </g>
        )}

        {/* Le filet qui tombe : des grains, pas un trait. Il s'arrête avec l'écoulement. */}
        {coule && (
          <line
            x1="12"
            y1="12.4"
            x2="12"
            y2={BAS_Y - ecoule * HAUTEUR}
            stroke={couleur}
            strokeWidth="0.7"
            strokeLinecap="round"
            strokeDasharray="0.6 1.1"
            className={styles.filet}
          />
        )}

        <path
          d={AMPOULE_HAUT}
          fill="none"
          stroke={couleur}
          strokeWidth="1.15"
          strokeLinejoin="round"
        />
        <path
          d={AMPOULE_BAS}
          fill="none"
          stroke={couleur}
          strokeWidth="1.15"
          strokeLinejoin="round"
        />
        <path
          d={`M5 ${HAUT_Y - 0.4} H19 M5 ${BAS_Y + 0.4} H19`}
          stroke={couleur}
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
      <span className={styles.reste} style={{ color: enRetard ? couleur : 'var(--text-muted)' }}>
        {libelle}
      </span>
    </span>
  );
}
